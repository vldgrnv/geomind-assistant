from dotenv import load_dotenv
from yandex_gpt import ask
from prompt import build_prompt

load_dotenv()

prompt = build_prompt()

print("Отправляю запрос в YandexGPT...\n")
answer = ask(prompt)
print(answer)
