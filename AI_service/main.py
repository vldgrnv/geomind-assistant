import os
import re
from dotenv import load_dotenv

try:
    from .search_algorithm import search
    from .classifier import classify_with_gpt
    from .prompt import build_answer_prompt
    from .yandex_gpt import ask
except ImportError:
    from search_algorithm import search
    from classifier import classify_with_gpt
    from prompt import build_answer_prompt
    from yandex_gpt import ask

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

THRESHOLD = 0.45

_GREETING_PAT = re.compile(r"^[\s]*привет[\s]*[!?.…]*[\s]*$", re.IGNORECASE)

_HELLO_REPLY = (
    "Привет! Рад вас видеть. Я GeoMind Assistant — помогу разобраться с ГИС-алгоритмами "
    "и геодезическими задачами. Напишите, что нужно посчитать или уточнить, "
    "можно простыми словами — подберу подходящий способ решения.")


def handle(user_query):
    if _GREETING_PAT.match(user_query or ""):
        print("[0/4] Приветствие — короткий ответ без поиска")
        return _HELLO_REPLY

    results = search(user_query, top_n=1)
    best_path, best_score = results[0]
    print(f"[1/4] Поиск: лучший результат — {best_path} (score={best_score:.3f})")

    if best_score >= THRESHOLD:
        algo_path = best_path
        print(f"[2/4] Score >= {THRESHOLD} → используем найденный алгоритм")
    else:
        print(f"[2/4] Score < {THRESHOLD} → отправляем в GPT-классификатор")
        algo_path = classify_with_gpt(user_query)
        if not algo_path:
            print("[3/4] GPT-классификатор: подходящий алгоритм НЕ найден")
            return "К сожалению, подходящий алгоритм не найден. Уточните запрос."
        print(f"[3/4] GPT-классификатор определил: {algo_path}")

    print(f"[3/4] Читаю алгоритм: {algo_path}")
    with open(algo_path, encoding="utf-8") as f:
        algorithm_text = f.read()

    print("[4/4] Отправляю итоговый промт в YandexGPT...")
    prompt = build_answer_prompt(user_query, algorithm_text)
    return ask(prompt)


if __name__ == "__main__":
    query = input("Введите вопрос: ")
    print("\nИщу алгоритм...\n")
    answer = handle(query)
    print(answer)


# Запуск сайта http://127.0.0.1:8000/
# python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload