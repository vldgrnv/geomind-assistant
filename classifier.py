import glob
import re

from yandex_gpt import ask


def _collect_metadata():
    """Собирает название, ключевые слова и примеры промтов из каждого .md файла."""
    blocks = []
    for path in sorted(glob.glob("algorithms/*.md")):
        with open(path, encoding="utf-8") as f:
            text = f.read()

        lines = text.splitlines()
        title = lines[0][2:].strip() if lines and lines[0].startswith("# ") else path

        keywords, examples = "", []
        section = None
        for line in lines:
            if re.match(r"^##\s*2\.\s*Ключевые слова", line, re.IGNORECASE):
                section = "kw"
                continue
            if re.match(r"^##\s*7\.\s*Примеры формулировок", line, re.IGNORECASE):
                section = "ex"
                continue
            if line.startswith("## ") and section:
                section = None
                continue
            if section == "kw" and line.strip():
                keywords = line.strip()
            if section == "ex" and line.strip().startswith("- "):
                examples.append(line.strip("- «»").strip())

        blocks.append({
            "path": path,
            "title": title,
            "keywords": keywords,
            "examples": examples,
        })
    return blocks


def classify_with_gpt(user_query):
    """Отправляет промт с метаданными алгоритмов в GPT для классификации.
    Возвращает путь к .md файлу или None."""
    blocks = _collect_metadata()

    listing = ""
    titles = []
    for b in blocks:
        titles.append(b["title"])
        listing += f"\n### {b['title']}\n"
        listing += f"Ключевые слова: {b['keywords']}\n"
        if b["examples"]:
            listing += "Примеры: " + "; ".join(b["examples"][:3]) + "\n"

    prompt = (
        f"Вопрос пользователя: «{user_query}»\n\n"
        f"Вот список алгоритмов геообработки:\n{listing}\n"
        f"Определи, к какому ОДНОМУ алгоритму относится вопрос. "
        f"Ответь ТОЛЬКО названием алгоритма из списка. "
        f"Если вопрос не относится ни к одному — ответь «НЕТ»."
    )

    answer = ask(prompt)

    for b in blocks:
        if b["title"].lower() in answer.lower():
            return b["path"]
    return None
