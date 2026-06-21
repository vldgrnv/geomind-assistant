import os
import re
import time
import logging
from dotenv import load_dotenv

try:
    from .search_algorithm import get_algorithm_text, search
    from .classifier import classify_with_gpt
    from .prompt import build_answer_prompt
    from .yandex_gpt import ask
    from .hardcoded_prompts import match_hardcoded
except ImportError:
    from search_algorithm import get_algorithm_text, search
    from classifier import classify_with_gpt
    from prompt import build_answer_prompt
    from yandex_gpt import ask
    from hardcoded_prompts import match_hardcoded

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

THRESHOLD = 0.45
logger = logging.getLogger("geomind.ai")

_GREETING_PAT = re.compile(r"^[\s]*привет[\s]*[!?.…]*[\s]*$", re.IGNORECASE)

_HELLO_REPLY = (
    "Привет! Рад вас видеть. Я GeoMind Assistant — помогу разобраться с ГИС-алгоритмами "
    "и геодезическими задачами. Напишите, что нужно посчитать или уточнить, "
    "можно простыми словами — подберу подходящий способ решения.")


def handle(user_query):
    started_at = time.perf_counter()
    hardcoded = match_hardcoded(user_query or "")
    if hardcoded:
        logger.info("ask_path=hardcoded duration_ms=%.2f", (time.perf_counter() - started_at) * 1000)
        return hardcoded

    if _GREETING_PAT.match(user_query or ""):
        logger.info("ask_path=greeting duration_ms=%.2f", (time.perf_counter() - started_at) * 1000)
        return _HELLO_REPLY

    search_started_at = time.perf_counter()
    results = search(user_query, top_n=1)
    best_path, best_score = results[0]
    search_duration_ms = (time.perf_counter() - search_started_at) * 1000
    logger.info(
        "search_completed best_path=%s score=%.3f duration_ms=%.2f",
        best_path,
        best_score,
        search_duration_ms,
    )

    if best_score >= THRESHOLD:
        algo_path = best_path
        logger.info("search_threshold_hit threshold=%.2f", THRESHOLD)
    else:
        logger.info("search_threshold_miss threshold=%.2f", THRESHOLD)
        classifier_started_at = time.perf_counter()
        algo_path = classify_with_gpt(user_query)
        classifier_duration_ms = (time.perf_counter() - classifier_started_at) * 1000
        if not algo_path:
            logger.info("classifier_no_match duration_ms=%.2f", classifier_duration_ms)
            return "К сожалению, подходящий алгоритм не найден. Уточните запрос."
        logger.info("classifier_match path=%s duration_ms=%.2f", algo_path, classifier_duration_ms)

    algorithm_text = get_algorithm_text(algo_path)

    llm_started_at = time.perf_counter()
    prompt = build_answer_prompt(user_query, algorithm_text)
    answer = ask(prompt)
    logger.info(
        "ask_completed path=%s total_duration_ms=%.2f llm_duration_ms=%.2f",
        algo_path,
        (time.perf_counter() - started_at) * 1000,
        (time.perf_counter() - llm_started_at) * 1000,
    )
    return answer


if __name__ == "__main__":
    query = input("Введите вопрос: ")
    print("\nИщу алгоритм...\n")
    answer = handle(query)
    print(answer)


# Запуск сайта http://127.0.0.1:8000/
# python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
