from openai import OpenAI

client = OpenAI()

# 모델 호출
response = client.chat.completions.create(
    model="gpt-5.5",
    messages=[
        {"role": "system", "content": "당신은 친절한 AI 비서입니다."},
        {"role": "user", "content": "안녕하세요! OpenAI API 테스트입니다."}
    ]
)

# 결과 출력
print(response.choices[0].message.content)