import glob
import os
import re
from dataclasses import dataclass

import pymorphy3
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
morph = pymorphy3.MorphAnalyzer()
ALGORITHMS_GLOB = os.path.join(BASE_DIR, "algorithms/*.md")

# ---------- Словарь синонимов (ГИС-домен) ----------
SYNONYMS = {
    # === buffer_analysis ===
    'буферная зона': 'буфер буферный proximity охранная санитарная радиус расстояние',
    'охранная зона': 'буфер буферный защитная санитарная радиус водоохранная',
    'санитарная зона': 'буфер буферный охранная защитная радиус',
    'зона влияния': 'буфер буферный proximity радиус доступность',
    'радиус': 'буфер буферный расстояние proximity',
    'пешеходная доступность': 'буфер буферный радиус расстояние',

    # === clip_analysis ===
    'обрезка': 'clip клиппинг вырезать выделить маска',
    'вырезать по границе': 'clip обрезка клиппинг маска территория',
    'выделить по маске': 'clip обрезка клиппинг',
    'клиппинг': 'clip обрезка вырезать маска',

    # === dissolve_analysis ===
    'агрегирование': 'dissolve объединение агрегация генерализация слияние',
    'генерализация': 'dissolve объединение агрегация упрощение',
    'объединить кварталы': 'dissolve агрегация слияние объединение район',
    'слить полигоны': 'dissolve слияние объединение агрегация',

    # === erase_analysis ===
    'стирание': 'erase вычитание удалить разность difference',
    'вычитание': 'erase стирание удалить разность difference исключение',
    'удалить по маске': 'erase вычитание стирание исключение',
    'исключение': 'erase вычитание разность difference',

    # === identity_analysis ===
    'тождественное наложение': 'identity обогащение привязка наложение',
    'обогащение данных': 'identity наложение привязка',
    'наложение с сохранением': 'identity обогащение overlay',

    # === interpolation_idw ===
    'интерполяция': 'idw обратные расстояния поверхность растр kriging кригинг',
    'поверхность': 'интерполяция idw растр',
    'карта загрязнения': 'интерполяция idw поверхность концентрация',
    'карта шума': 'интерполяция idw поверхность',
    'карта осадков': 'интерполяция idw поверхность температура',
    'грунтовые воды': 'интерполяция idw поверхность скважины',

    # === intersect_analysis ===
    'пересечение': 'intersect overlay наложение зона совпадения перекрытие',
    'наложение': 'intersect overlay пересечение union identity',
    'зона совпадения': 'intersect пересечение overlay перекрытие',
    'перекрытие': 'intersect overlay пересечение',

    # === merge_analysis ===
    'объединение слоёв': 'merge слияние консолидация агрегация',
    'слияние слоёв': 'merge объединение консолидация',
    'объединить слои': 'merge слияние консолидация',
    'консолидация': 'merge объединение слияние',
    'объединить шейпфайлы': 'merge слияние shapefile',

    # === spatial_join ===
    'пространственное соединение': 'spatial join привязка присоединение атрибуты',
    'присоединение': 'spatial join привязка соединение',
    'привязка точек': 'spatial join присоединение пространственное соединение',
    'привязать к районам': 'spatial join присоединение пространственное',
    'ближайший объект': 'spatial join closest привязка',

    # === symdiff_analysis ===
    'симметричная разность': 'symdiff symmetric difference различия XOR',
    'различия между картами': 'symdiff симметричная разность сравнение динамика',
    'сравнение карт': 'symdiff симметричная разность различия расхождения',
    'расхождения': 'symdiff различия сравнение динамика',
    'динамика изменений': 'symdiff различия сравнение',

    # === union_analysis ===
    'объединение с наложением': 'union overlay полное покрытие зонирование',
    'полное покрытие': 'union overlay объединение наложение',
    'зонирование': 'union overlay полное покрытие конфликт',

    # === update_analysis ===
    'обновление': 'update актуализация замещение замена',
    'актуализация': 'update обновление замена замещение',
    'замена данных': 'update обновление актуализация замещение',
    'заменить границы': 'update обновление актуализация',

    # === кросс-алгоритмические связи ===
    'объединение': 'merge union dissolve слияние агрегация',
    'слияние': 'merge union dissolve объединение',
    'вырезать': 'clip erase обрезка вычитание',
}


def lemmatize(text):
    """Лемматизация текста через pymorphy3."""
    words = re.findall(r'[а-яёa-z0-9]+', text.lower())
    return ' '.join(morph.parse(w)[0].normal_form for w in words)


def expand_query(query):
    """Расширяет запрос синонимами из словаря."""
    q_lower = query.lower()
    extra = []
    for trigger, syns in SYNONYMS.items():
        if trigger in q_lower:
            extra.append(syns)
    return query + ' ' + ' '.join(extra) if extra else query


def _extract_sections(text):
    """Извлекает заголовок, ключевые слова, примеры, область применения
    и подзаголовки программной реализации из md-файла.
    Секции взвешены: заголовок и ключевые слова — x3, примеры — x2."""
    lines = text.splitlines()
    title = ""
    keywords = ""
    examples = []
    application = []
    implementation = []

    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()

    kw_pattern = re.compile(r"^##\s*2\.\s*Ключевые слова", re.IGNORECASE)
    ex_pattern = re.compile(r"^##\s*7\.\s*Примеры формулировок", re.IGNORECASE)
    app_pattern = re.compile(r"^##\s*3\.\s*Область применения", re.IGNORECASE)
    impl_pattern = re.compile(r"^##\s*6\.\s*Программная реализация", re.IGNORECASE)

    section = None
    for line in lines:
        if kw_pattern.match(line):
            section = "kw"
            continue
        if ex_pattern.match(line):
            section = "ex"
            continue
        if app_pattern.match(line):
            section = "app"
            continue
        if impl_pattern.match(line):
            section = "impl"
            continue
        if line.startswith("## ") and section:
            section = None
            continue

        if section == "kw" and line.strip():
            keywords = line.strip()
        if section == "ex" and line.strip().startswith("- "):
            examples.append(line.strip("- «»").strip())
        if section == "app" and line.strip().startswith("- "):
            application.append(line.strip("- ").strip())
        if section == "impl" and line.strip().startswith("###"):
            implementation.append(line.strip("# ").strip())

    # Взвешивание: заголовок и ключевые слова x3, примеры x2
    weighted = (
        f"{title} " * 3
        + f"{keywords} " * 3
        + ((' '.join(examples) + ' ') * 2)
        + ' '.join(application) + ' '
        + ' '.join(implementation)
    )
    return weighted


def load_algorithms(apply_lemma=True):
    """Загружает все md-файлы. Возвращает (тексты, пути).
    Если apply_lemma=True — лемматизирует тексты."""
    docs, paths = [], []
    for path in sorted(glob.glob(os.path.join(BASE_DIR, "algorithms/*.md"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        doc = _extract_sections(text)
        if apply_lemma:
            doc = lemmatize(doc)
        docs.append(doc)
        paths.append(path)
    return docs, paths


@dataclass
class AlgorithmIndex:
    version: tuple[tuple[str, int], ...]
    docs_lemma: list[str]
    paths: list[str]
    raw_texts: dict[str, str]
    tfidf_vectorizer: TfidfVectorizer
    tfidf_docs_matrix: object
    bm25: BM25Okapi


_INDEX_CACHE: AlgorithmIndex | None = None


def _algorithms_version():
    version = []
    for path in sorted(glob.glob(ALGORITHMS_GLOB)):
        version.append((path, int(os.path.getmtime(path))))
    return tuple(version)


def _build_index() -> AlgorithmIndex:
    docs_lemma = []
    paths = []
    raw_texts = {}
    for path in sorted(glob.glob(ALGORITHMS_GLOB)):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        raw_texts[path] = text
        docs_lemma.append(lemmatize(_extract_sections(text)))
        paths.append(path)

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
        max_df=0.9,
    )
    tfidf_docs_matrix = vectorizer.fit_transform(docs_lemma)
    bm25 = BM25Okapi([doc.split() for doc in docs_lemma])

    return AlgorithmIndex(
        version=_algorithms_version(),
        docs_lemma=docs_lemma,
        paths=paths,
        raw_texts=raw_texts,
        tfidf_vectorizer=vectorizer,
        tfidf_docs_matrix=tfidf_docs_matrix,
        bm25=bm25,
    )


def get_algorithm_index() -> AlgorithmIndex:
    global _INDEX_CACHE
    current_version = _algorithms_version()
    if _INDEX_CACHE is None or _INDEX_CACHE.version != current_version:
        _INDEX_CACHE = _build_index()
    return _INDEX_CACHE


def get_algorithm_text(path):
    return get_algorithm_index().raw_texts[path]


def _normalize(arr):
    """Min-max нормализация массива в [0, 1]."""
    mn, mx = arr.min(), arr.max()
    if mx - mn < 1e-9:
        return np.zeros_like(arr)
    return (arr - mn) / (mx - mn)


def search(query, top_n=3):
    """Комбинированный поиск: TF-IDF (биграммы) + BM25.
    Возвращает список (путь, score) для top_n результатов."""
    index = get_algorithm_index()

    # Расширяем запрос синонимами, затем лемматизируем
    expanded = expand_query(query)
    q_lemma = lemmatize(expanded)

    query_tfidf = index.tfidf_vectorizer.transform([q_lemma])
    tfidf_scores = cosine_similarity(query_tfidf, index.tfidf_docs_matrix)[0]

    bm25_scores = np.array(index.bm25.get_scores(q_lemma.split()))

    # --- Комбинированный скор ---
    combined = 0.5 * _normalize(tfidf_scores) + 0.5 * _normalize(bm25_scores)

    top_idxs = combined.argsort()[::-1][:top_n]
    return [(index.paths[i], combined[i]) for i in top_idxs]


if __name__ == "__main__":
    test_queries = [
        'Как построить буферную зону вокруг линейного объекта в QGIS с учётом исключений по атрибутам?',
        'Как правильно настроить интерполяцию с анизотропией для данных о загрязнении почвы?',
        'Как объединить несколько слоёв в один?',
        'Как вырезать территорию по границе района?',
        'Как найти пересечение двух полигональных слоёв?',
    ]

    for q in test_queries:
        results = search(q)
        print(f"\nЗапрос: {q}")
        print(f"{'='*70}")
        for path, score in results:
            print(f"  {score:.3f}  {path}")
        print()
