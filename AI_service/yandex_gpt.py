import os
import time

import requests


def ask(prompt):
    api_key = os.environ["YANDEX_API_KEY"]
    folder_id = os.environ["YANDEX_FOLDER_ID"]
    payload = {
        "modelUri": f"gpt://{folder_id}/yandexgpt-lite/latest",
        "completionOptions": {"temperature": 0.3, "maxTokens": 2000},
        "messages": [
            {"role": "system", "text": "Ты — ассистент для ГИС-специалистов."},
            {"role": "user", "text": prompt},
        ],
    }
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {"Authorization": f"Api-Key {api_key}"}
    last_error = None

    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=(5, 60))
            if resp.status_code >= 500:
                last_error = RuntimeError(f"Yandex API {resp.status_code}: {resp.text[:500]}")
            else:
                resp.raise_for_status()
                return resp.json()["result"]["alternatives"][0]["message"]["text"]
        except requests.RequestException as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))

    raise RuntimeError("Yandex GPT temporarily unavailable") from last_error
