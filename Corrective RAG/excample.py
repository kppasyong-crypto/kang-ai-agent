import os
import json
from typing import TypedDict, List, Literal
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_core.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langgraph.graph import StateGraph, END


def build_pgvector_connection_string() -> str:
    connection_string = os.getenv("PGVECTOR_CONNECTION_STRING") or os.getenv("DATABASE_URL")
    if connection_string:
        return connection_string

    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")

    if not all([host, database, user, password]):
        raise ValueError(
            "PGVECTOR_CONNECTION_STRING 또는 DATABASE_URL, "
            "또는 POSTGRES_HOST/POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD를 설정해주세요."
        )

    return (
        f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}"
    )

# --- 0. 환경 설정 ---
load_dotenv()
print("=" * 80)
print("LangGraph를 사용한 Corrective RAG (CRAG) 시스템")
print("=" * 80)

# SERPER_API_KEY가 환경 변수에 설정되어 있어야 합니다.
if os.getenv("SERPER_API_KEY") is None:
    print("[경고] SERPER_API_KEY가 설정되지 않았습니다. Web Search가 작동하지 않습니다.")

# =================================================================
#  Part 1: 데이터 준비 및 Retriever/Tool 생성
# =================================================================
print("\n[Part 1] 데이터 준비 및 도구 생성")
print("-" * 80)

# 1. 문서 로드 및 분할 (예시 PDF 사용)
try:
    FILE_PATH = Path("data") / "SPRi AI Brief_10월호_산업동향_1002_F.pdf"
    loader = PyPDFLoader(str(FILE_PATH))
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(documents)
    print(f"'{os.path.basename(FILE_PATH)}' 문서를 {len(splits)}개의 청크로 분할 완료.")

    # 2. 임베딩 및 Vector DB 저장
    embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")
    CONNECTION_STRING = build_pgvector_connection_string()
    COLLECTION_NAME = "crag_example"

    vectorstore = PGVector.from_documents(
        documents=splits,
        embedding=embeddings_model,
        collection_name=COLLECTION_NAME,
        connection=CONNECTION_STRING,
        pre_delete_collection=True,
    )
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})
    print(f"Vector DB에 데이터 저장 및 Retriever 생성 완료.")

except Exception as e:
    print(f"[오류] 데이터 준비 중 문제가 발생했습니다: {e}")
    print("PDF 파일 경로와 Postgres 연결 환경 변수를 확인해주세요.")
    exit()

# 3. Web Search 도구 정의
@tool
def web_search(query: str):
    """웹 검색을 수행하여 최신 정보를 얻습니다."""
    search = GoogleSerperAPIWrapper()
    results = search.run(query)
    return results

# ============================================================
#  Part 2: LangGraph 설계 (상태, 노드, 엣지 정의)
# ============================================================
print("\n[Part 2] LangGraph 설계")
print("-" * 80)

# --- 2-1. 그래프 상태 (State) 정의 ---
class GraphState(TypedDict):
    question: str
    documents: List[Document]
    generation: str
    is_relevant: str # 문서 관련성 평가 결과 ('yes' or 'no')


class DocumentRelevanceGrade(BaseModel):
    score: Literal["yes", "no"] = Field(description="문서가 질문과 관련 있으면 'yes', 아니면 'no'")

# --- 2-2. 노드(Node) 함수 정의 ---
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def retrieve(state: GraphState):
    """Vector DB에서 문서를 검색합니다."""
    print("--- 노드 실행: retrieve ---")
    question = state["question"]
    documents = retriever.invoke(question)
    return {"documents": documents}

def grade_documents(state: GraphState):
    """검색된 문서가 질문과 관련이 있는지 평가합니다."""
    print("--- 노드 실행: grade_documents ---")
    question = state["question"]
    documents = state["documents"]

    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 문서 평가 전문가입니다. 주어진 문서가 사용자의 질문에 답변하기에 관련성이 있는지 평가해주세요.
        'yes' 또는 'no'로만 답변해야 합니다.

        질문: {question}
        
        문서 내용:
        {documents}
        """),
    ])
    
    # JSON 출력을 위한 LLM 설정
    structured_llm_grader = llm.with_structured_output(DocumentRelevanceGrade)
    
    # 문서 내용을 하나의 문자열로 결합
    doc_str = "\n\n".join(doc.page_content for doc in documents)
    
    chain = prompt | structured_llm_grader
    response = chain.invoke({"question": question, "documents": doc_str})
    
    score = response.score.lower()
    print(f"   문서 관련성 평가 결과: {score}")
    return {"is_relevant": score}

def generate(state: GraphState):
    """검색된 정보를 바탕으로 답변을 생성합니다."""
    print("--- 노드 실행: generate ---")
    question = state["question"]
    documents = state["documents"]
    
    prompt = ChatPromptTemplate.from_template("""
    주어진 문맥 정보를 사용하여 다음 질문에 답변해주세요.
    
    질문: {question}
    
    문맥:
    {context}
    """)
    
    context = "\n\n".join(doc.page_content for doc in documents)
    chain = prompt | llm | StrOutputParser()
    generation = chain.invoke({"context": context, "question": question})
    
    return {"generation": generation}

def transform_query(state: GraphState):
    """웹 검색에 더 적합하도록 질문을 재구성합니다."""
    print("--- 노드 실행: transform_query ---")
    question = state["question"]
    
    prompt = ChatPromptTemplate.from_template("""
    당신은 쿼리 생성 전문가입니다. 사용자의 질문을 웹 검색에 더 효과적인 검색어로 재구성해주세요.
    재구성된 검색어만 반환해야 합니다.

    원래 질문: {question}
    """)
    
    chain = prompt | llm | StrOutputParser()
    better_question = chain.invoke({"question": question})
    
    print(f"   재구성된 질문: {better_question}")
    return {"question": better_question}

def web_search_node(state: GraphState):
    """재구성된 질문으로 웹 검색을 수행합니다."""
    print("--- 노드 실행: web_search_node ---")
    question = state["question"]
    
    search_result = web_search.invoke(question)
    
    # 웹 검색 결과를 Document 객체로 변환
    web_documents = [Document(page_content=search_result)]
    
    return {"documents": web_documents}

# --- 2-3. 조건부 엣지(Edge) 함수 정의 ---
def decide_to_generate(state: GraphState):
    """문서 평가 결과에 따라 다음 노드를 결정합니다."""
    print("--- 조건부 엣지 실행: decide_to_generate ---")
    if state["is_relevant"] == "yes":
        print("   (결정) 문서 관련성 높음 -> generate")
        return "generate"
    else:
        print("   (결정) 문서 관련성 낮음 -> transform_query (교정 단계)")
        return "transform_query"

# --- 2-4. 그래프 생성 및 연결 ---
workflow = StateGraph(GraphState)

workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("generate", generate)
workflow.add_node("transform_query", transform_query)
workflow.add_node("web_search_node", web_search_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges("grade_documents", decide_to_generate, {
    "generate": "generate",
    "transform_query": "transform_query",
})
workflow.add_edge("transform_query", "web_search_node")
workflow.add_edge("web_search_node", "generate")
workflow.add_edge("generate", END)

app = workflow.compile()
print("\nCRAG 그래프 컴파일 완료!")
try:
    img_bytes = app.get_graph().draw_mermaid_png()
    with open("crag_graph.png", "wb") as f:
        f.write(img_bytes)
    print("그래프 구조를 'crag_graph.png' 파일로 저장했습니다.")
except Exception as e:
    print(f"그래프 시각화 실패 (Graphviz 필요): {e}")

# ============================================================
#  Part 3: CRAG 시스템 실행
# ============================================================
print("\n" + "=" * 80)
print("Corrective RAG 시스템을 시작합니다.")
print("종료하려면 'quit' 또는 'exit'를 입력하세요.")
print("=" * 80)

while True:
    user_question = input("\nYou: ").strip()
    if user_question.lower() in ['quit', 'exit', '종료']:
        print("\n시스템을 종료합니다.")
        break
    if not user_question:
        continue

    inputs = {"question": user_question}
    try:
        response = app.invoke(inputs)
        print(f"\nAI: {response['generation']}")
        print("-" * 80)
    except Exception as e:
        print(f"\n[오류 발생] {e}")