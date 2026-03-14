import os
import requests


def ask(prompt):
    api_key = os.environ["YANDEX_API_KEY"]
    folder_id = os.environ["YANDEX_FOLDER_ID"]

    resp = requests.post(
        "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
        headers={"Authorization": f"Api-Key {api_key}"},
        json={
            "modelUri": f"gpt://{folder_id}/yandexgpt-lite/latest",
            "completionOptions": {"temperature": 0.3, "maxTokens": 2000},
            "messages": [
                {"role": "system", "text": "Ты — ассистент для ГИС-специалистов."},
                {"role": "user", "text": prompt},
            ],
        },
    )
    if resp.status_code != 200:
        print("Ошибка API:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()["result"]["alternatives"][0]["message"]["text"]
