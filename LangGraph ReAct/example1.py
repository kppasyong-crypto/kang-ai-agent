from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# 환경 변수 로드 (.env 파일에서 OPENAI_API_KEY 등 로드)
load_dotenv()

# 상태 정의 (TypedDict 사용)
class AgentState(TypedDict):
    question: str
    action: str
    observation: str
    retry: int

# Reason 노드
def reason(state: AgentState):

    llm = ChatOpenAI(model="gpt-5.4-mini")
    prompt = f"Q: {state.get('question')}\n어떤 행동을 해야 답을 찾을 수 있을까?"
    res = llm.invoke(prompt)
    action = res.content.strip()
    print(f"[Reason] 결정된 행동: {action}")
    return {"action": action}

# Act 노드
def act(state: AgentState):
    action = state.get("action", "")
    if "날씨" in action:
        observation = "서울의 날씨는 맑음 ☀️"
    else:
        observation = "적절한 도구를 찾지 못함"
    print(f"[Act] 관찰 결과: {observation}")
    return {"observation": observation}

# Observe 노드 (단순 상태 변경 담당: retry 횟수 증가 등)
def observe(state: AgentState):
    retry = state.get("retry", 0)
    # 다음 턴을 위해 retry 횟수만 1 증가
    return {"retry": retry + 1}

# 조건부 엣지 라우팅 함수
def should_continue(state: AgentState):
    observation = state.get("observation", "")
    # observe 노드 실행 후 결과이므로 통과 전 retry가 증가되어 있으나 여기선 상관없음
    retry = state.get("retry", 0)
    
    if "맑음" in observation or retry >= 1:
        print("[Observe] 결과 만족. 종료합니다.")
        return "finish"
    
    print("[Observe] 결과 불만족. 다시 Reason 단계로.")
    return "reason"

# 그래프 구성
graph = StateGraph(AgentState)
graph.add_node("reason", reason)
graph.add_node("act", act)
graph.add_node("observe", observe)

graph.add_edge("reason", "act")
graph.add_edge("act", "observe")

# observe 노드 이후 어떤 경로로 갈지 결정하는 조건부 엣지
graph.add_conditional_edges(
    "observe",
    should_continue,
    {
        "finish": END,
        "reason": "reason"
    }
)

graph.set_entry_point("reason")

app = graph.compile()

# 초기 상태 설정
initial_state = {
    "question": "서울의 날씨 알려줘",
    "action": "",
    "observation": "",
    "retry": 0
}

if __name__ == "__main__":
    result = app.invoke(initial_state)
    print("\n최종 상태:")
    print(result)