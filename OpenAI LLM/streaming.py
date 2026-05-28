from openai import OpenAI

client = OpenAI()

stream = client.chat.completions.create(
    model="gpt-5.5",
    messages=[
        {"role": "user", "content": "kamis 오늘가장 하락한 식품으로 식단표 짜줘 그리고 조리방법까지 말해줘"}
    ],
    stream=True
)

for chunk in stream:
    delta = chunk.choices[0].delta

    if delta.content:
        print(delta.content, end="")