import operator
from typing import TypedDict, Annotated, Optional
from langgraph.graph import StateGraph, START, END
from datetime import datetime

'''
LangGraph의 "조건부 라우팅(Conditional Edge)"이
잘 동작하는지 보여주기 위해 의도적으로 작성된 예외 처리 테스트 결과
'''

class WorkflowState(TypedDict):
    input_data: str
    processing_stage: str
    results: Annotated[list, operator.add]
    error: Optional[str]
    metadata: dict

# 노드 함수들 정의
def validate_input(state: WorkflowState) -> dict:
    """입력 검증 노드"""
    input_data = state["input_data"]

    if not input_data:
        return {
            "error": "입력 데이터가 비어있습니다",
            "processing_stage": "validation_failed"
        }

    if len(input_data) > 1000:
        return {
            "error": "입력 데이터가 너무 깁니다",
            "processing_stage": "validation_failed"
        }

    return {
        "processing_stage": "validated",
        "results": ["입력 검증 완료"]
    }

def process_data(state: WorkflowState) -> dict:
    """데이터 처리 노드"""
    # 실제 처리 로직
    processed = state["input_data"].upper()

    return {
        "processing_stage": "processed",
        "results": [f"처리 결과: {processed}"],
        "metadata": {
            **state.get("metadata", {}),
            "processed_at": datetime.now().isoformat()
        }
    }

def generate_output(state: WorkflowState) -> dict:
    """출력 생성 노드"""
    final_output = "\n".join(state["results"])

    return {
        "processing_stage": "completed",
        "results": [f"최종 출력: {final_output}"],
        "metadata": {
            **state["metadata"],
            "completed_at": datetime.now().isoformat()
        }
    }

def handle_error(state: WorkflowState) -> dict:
    """에러 처리 노드"""
    return {
        "processing_stage": "error_handled",
        "results": [f"에러 처리: {state['error']}"]
    }

# 라우팅 함수
def route_after_validation(state: WorkflowState) -> str:
    """검증 후 라우팅"""
    if state.get("error"):
        return "error"
    return "process"

# 그래프 구성
workflow = StateGraph(WorkflowState)

# 노드 추가
workflow.add_node("validate", validate_input)
workflow.add_node("process", process_data)
workflow.add_node("output", generate_output)
workflow.add_node("error_handler", handle_error)

# 엣지 추가
workflow.add_edge(START, "validate")
workflow.add_conditional_edges(
    "validate",
    route_after_validation,
    {
        "process": "process",
        "error": "error_handler"
    }
)
workflow.add_edge("process", "output")
workflow.add_edge("output", END)
workflow.add_edge("error_handler", END)

# 그래프 컴파일
app = workflow.compile()


# 그래프 실행
if __name__ == "__main__":
    print("--- 정상적인 입력 텍스트 ---")
    inputs = {
        "input_data": "Hello LangGraph!",
        "processing_stage": "start",
        "results": [],
        "error": None,
        "metadata": {}
    }
    
    # app.stream 을 사용하여 그래프 실행 결과를 순차적으로 출력
    for output in app.stream(inputs):
        for key, value in output.items():
            print(f"[{key}] 노드 실행 결과:")
            print(value)
            print("-" * 30)

    print("\n--- 예외 처리 분기 라우팅 테스트 (의도적인 빈 문자열 입력) ---")
    inputs_error = {
        "input_data": "케이뱅크",  ## 빈 문자열 입력 혹은 문자열을 입력해보십시오
        "processing_stage": "start",
        "results": [],
        "error": None,
        "metadata": {}
    }
    
    for output in app.stream(inputs_error):
        for key, value in output.items():
            print(f"[{key}] 노드 실행 결과:")
            print(value)
            print("-" * 30)