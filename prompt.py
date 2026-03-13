import glob


def build_prompt():
    headers = []
    for path in sorted(glob.glob("algorithms/*.md")):
        with open(path, encoding="utf-8") as f:
            first_line = f.readline().strip()
        if first_line.startswith("# "):
            headers.append(first_line[2:])

    return (
        "Вот список алгоритмов геообработки пространственных данных:\n"
        + "\n".join(f"- {h}" for h in headers)
        + "\n\nКратко опиши назначение каждого алгоритма (1–2 предложения)."
    )


if __name__ == "__main__":
    print(build_prompt())
