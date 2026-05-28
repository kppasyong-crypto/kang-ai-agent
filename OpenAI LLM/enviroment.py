from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()

response = client.chat.completions.create(
    model="gpt-5.5",
    messages=[
        {"role": "user", "content": "환경변수 테스트"}
    ]
)

print(response.choices[0].message.content)