import random
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing import TypedDict

class GameState(TypedDict):
    answer: int       # 정답 숫자
    attempts: int     # 시도 횟수
    history: list     # 시도 기록
    game_over: bool   # 게임 종료 여부

def process_guess(state: GameState) -> dict:
    guess = int(input("1~10 사이 숫자를 입력하세요: "))
    attempts = state["attempts"] + 1
    history = state["history"] + [guess]

    if guess == state["answer"]:
        print(f"정답입니다! {attempts}번 만에 맞추셨습니다.")
        return {"attempts": attempts, "history": history, "game_over": True}
    elif guess < state["answer"]:
        print(f"더 큰 숫자입니다. (시도: {attempts}번)")
    else:
        print(f"더 작은 숫자입니다. (시도: {attempts}번)")

    return {"attempts": attempts, "history": history, "game_over": False}

def should_continue(state: GameState) -> str:
    return END if state["game_over"] else "guess"

graph = StateGraph(GameState)
graph.add_node("guess", process_guess)
graph.add_edge(START, "guess")
graph.add_conditional_edges("guess", should_continue)

memory = InMemorySaver()
app = graph.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "number_game"}}
answer = random.randint(1, 10)

print("=== 숫자 맞추기 게임 (1~10) ===")
result = app.invoke({"answer": answer, "attempts": 0, "history": [], "game_over": False}, config=config)

while not result["game_over"]:
    result = app.invoke({}, config=config)

print(f"\n--- 게임 결과 ---")
print(f"정답: {result['answer']}")
print(f"총 시도 횟수: {result['attempts']}번")
print(f"시도 기록: {result['history']}")
