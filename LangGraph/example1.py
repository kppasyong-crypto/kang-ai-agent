from typing import TypedDict
from langgraph.graph import StateGraph

# --- 1. 상태(State) 정의 ---
# 그래프 전체에서 공유될 데이터 구조를 정의합니다.
# 'value'라는 키에 정수(int) 값이 저장됩니다.
class GraphState(TypedDict):
    """
    그래프의 상태를 나타냅니다.

    Args:
        value (int): 0에서 시작하여 1씩 증가할 카운터 값
    """
    value: int

# --- 2. 노드(Node) 함수 정의 ---
# 각 노드는 현재 상태(state)를 입력으로 받고,
# 상태를 어떻게 변경할지(또는 변경하지 않을지) 딕셔너리 형태로 반환합니다.

def add_one(state: GraphState):
    """
    현재 상태의 'value' 값에 1을 더합니다.
    """
    # 현재 상태를 읽어옵니다.
    current_value = state['value']
    print(f"--- 'add_one' 노드 실행 ---")
    print(f"   (입력) 현재 상태 'value': {current_value}")
    
    # 상태를 변경합니다.
    new_value = current_value + 1
    
    print(f"   (출력) 'value'를 {new_value}로 업데이트")
    
    # 변경할 상태만 딕셔너리로 반환합니다.
    return {"value": new_value}

# --- 3. 조건부 엣지(Edge) 함수 정의 ---
# 이 함수는 현재 상태를 *읽고* 다음에 어떤 노드로 가야 할지 결정합니다.

def should_continue(state: GraphState):
    """
    상태의 'value' 값을 확인하여 다음 단계를 결정합니다.
    """
    current_value = state['value']
    print(f"\n--- 'should_continue' 조건부 엣지 실행 ---")
    print(f"   (상태 확인) 현재 'value': {current_value}")
    
    if current_value < 3:
        # 값이 3보다 작으면 'continue_adding' 경로를 반환
        print(f"   (결정) 값이 3보다 작으므로 'add_one' 노드로 다시 이동")
        return "continue_adding" 
    else:
        # 값이 3 이상이면 'end_graph' 경로를 반환
        print(f"   (결정) 값이 3 이상이므로 그래프 종료")
        return "end_graph"

# --- 4. 그래프 생성 및 노드/엣지 연결 ---

# GraphState를 사용하는 StateGraph 객체 생성
workflow = StateGraph(GraphState)

# 노드를 그래프에 추가 (이름, 실행할 함수)
workflow.add_node("adder_node", add_one)

# 그래프의 시작점을 'adder_node'로 설정
workflow.set_entry_point("adder_node")

# 조건부 엣지(간선) 추가
# 'adder_node'가 실행된 후, 'should_continue' 함수를 호출하여 상태를 확인
workflow.add_conditional_edges(
    "adder_node",           # 시작 노드
    should_continue,        # 상태를 확인할 함수
    {
        # 'should_continue'가 "continue_adding"을 반환하면 -> "adder_node"로 이동 (루프)
        "continue_adding": "adder_node",
        
        # 'should_continue'가 "end_graph"를 반환하면 -> 그래프 종료
        "end_graph": "__end__" 
    }
)

# --- 5. 그래프 컴파일 및 실행 ---

# 그래프를 실행 가능한 객체로 컴파일
app = workflow.compile()

print("--- 그래프 실행 시작 (초기 상태: {'value': 0}) ---")

# invoke: 그래프를 실행하고 최종 상태를 반환
# {'value': 0}으로 초기 상태를 설정하여 실행
final_state = app.invoke({"value": 0})

print("\n--- 그래프 실행 종료 ---")
print(f"최종 상태: {final_state}")