"""
book_recomender.py — рекомендатель казахских книг на эмбеддингах.

Что делает:
  - читает книги из books.csv (колонки name, description)
  - превращает аннотации в векторы многоязычной моделью (понимает казахский)
  - recommend(name)        -> похожие книги
  - searchByInterest(query)-> поиск по интересам на любом языке (для иностранцев)
  - сохраняет rec_vectors.npy / rec_names.npy для приложения app.py

Запуск как скрипта (демо):
    python book_recomender.py
"""
import os
import csv
import numpy as np
from sentence_transformers import SentenceTransformer

# файлы ищем рядом с этим скриптом, а не в текущей папке терминала
HERE = os.path.dirname(os.path.abspath(__file__))
BOOKS_CSV = os.path.join(HERE, "books.csv")
VECTORS_NPY = os.path.join(HERE, "rec_vectors.npy")
NAMES_NPY = os.path.join(HERE, "rec_names.npy")

# многоязычная модель: кладёт казахский, русский и английский в ОДНО пространство
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_books(path=BOOKS_CSV):
    "читает книги из csv; возвращает (names, descriptions)"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    names = [r["name"] for r in rows]
    descriptions = [r["description"] for r in rows]
    return names, descriptions


def embed(texts, model):
    "тексты -> нормализованные векторы (единичные, чтобы косинус = скалярное произведение)"
    return model.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)


def top_k(sims, k, skip=None):
    "индексы k наибольших значений sims, при желании пропуская индекс skip"
    order = np.argsort(-sims)
    order = [j for j in order if j != skip][:k]
    return order


class BookRecommender:
    "хранит книги и их векторы, умеет рекомендовать и искать по интересам"

    def __init__(self, model_name=MODEL):
        self.model = SentenceTransformer(model_name)
        self.names, self.descriptions = load_books()
        self.vectors = embed(self.descriptions, self.model)  # (n_books, 384), единичные

    # 1) похожие на конкретную книгу
    def recommend(self, name, topn=3):
        if name not in self.names:
            raise ValueError(f"нет такой книги: {name}")
        i = self.names.index(name)
        sims = self.vectors @ self.vectors[i]          # косинус ко всем книгам
        return [(self.names[j], float(sims[j])) for j in top_k(sims, topn, skip=i)]

    # 2) поиск по свободному запросу на любом языке
    def search_by_interest(self, query, topn=3):
        qv = embed([query], self.model)[0]
        sims = self.vectors @ qv
        return [(self.names[j], float(sims[j])) for j in top_k(sims, topn)]

    # 3) сохранить векторы для app.py
    def save(self):
        np.save(VECTORS_NPY, self.vectors)
        np.save(NAMES_NPY, np.array(self.names, dtype=object))
        return VECTORS_NPY, NAMES_NPY


def _demo():
    rec = BookRecommender()
    print(f"загружено книг: {len(rec.names)}\n")

    print("=== ПОХОЖИЕ НА КНИГУ ===")
    for name in ["Көшпенділер — Ілияс Есенберлин", "Бақытсыз Жамал — Міржақып Дулатов"]:
        print(f"похожие на «{name}»:")
        for other, score in rec.recommend(name):
            print(f"  {score:.3f}  {other}")
        print()

    print("=== ПОИСК ПО ИНТЕРЕСАМ (любой язык) ===")
    for query in ["a funny story about childhood and school",
                  "трагическая судьба женщины",
                  "тарих, хандар мен батырлар"]:
        print(f'запрос: "{query}"')
        for other, score in rec.search_by_interest(query):
            print(f"  {score:.3f}  {other}")
        print()

    paths = rec.save()
    print("сохранено:", ", ".join(os.path.basename(p) for p in paths))


if __name__ == "__main__":
    _demo()
