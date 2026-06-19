"""Сборка базы знаний для RAG.

Что делает по шагам:
  1) (опц.) скрейпит сайт фонда -> data/knowledge/site_docs.jsonl
  2) загружает твои файлы из data/raw_docs -> data/knowledge/file_docs.jsonl
  3) режет все документы на чанки
  4) считает embeddings (нужен EMBEDDINGS_API_KEY)
  5) сохраняет векторный индекс в data/index/

Примеры запуска (из папки day_5):
  python ingest.py                 # скрейпинг сайта + файлы + индекс
  python ingest.py --no-scrape     # только файлы из raw_docs + индекс
  python ingest.py --only-scrape   # только скачать сайт, без индекса
"""
import argparse
import json

from tqdm import tqdm

from src.config import KNOWLEDGE_DIR
from src.data_collection.load_files import load_files
from src.data_collection.scrape_site import scrape
from src.rag.chunking import chunk_text
from src.rag.embeddings import embed_texts
from src.rag.vector_store import VectorStore


def _load_docs() -> list[dict]:
    docs: list[dict] = []
    for path in (KNOWLEDGE_DIR / "site_docs.jsonl", KNOWLEDGE_DIR / "file_docs.jsonl"):
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        docs.append(json.loads(line))
    return docs


def build_index() -> None:
    docs = _load_docs()
    if not docs:
        print("Нет документов для индексации. Сначала собери данные (скрейпинг/файлы).")
        return

    # Документы -> чанки с метаданными
    chunk_texts: list[str] = []
    metadatas: list[dict] = []
    for doc in docs:
        for chunk in chunk_text(doc["text"]):
            chunk_texts.append(chunk)
            metadatas.append(
                {
                    "text": chunk,
                    "source": doc.get("source", ""),
                    "title": doc.get("title", ""),
                    "lang": doc.get("lang", "ru"),
                    "origin": doc.get("origin", "site"),  # 'file' = твой файл, 'site' = скрейп
                }
            )

    print(f"Документов: {len(docs)} -> чанков: {len(chunk_texts)}")
    print("Считаю embeddings (это может занять время и требует EMBEDDINGS_API_KEY)...")

    store = VectorStore()
    # Эмбеддим и добавляем порциями, чтобы видеть прогресс
    step = 256
    for i in tqdm(range(0, len(chunk_texts), step), desc="Embeddings", unit="батч"):
        batch_texts = chunk_texts[i : i + step]
        batch_meta = metadatas[i : i + step]
        vectors = embed_texts(batch_texts)
        store.add(vectors, batch_meta)

    store.save()
    print(f"Готово! Индекс сохранён: {len(store)} фрагментов -> data/index/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Сборка базы знаний для RAG-бота")
    parser.add_argument("--no-scrape", action="store_true", help="не скрейпить сайт")
    parser.add_argument(
        "--only-scrape", action="store_true", help="только скрейпинг, без индекса"
    )
    args = parser.parse_args()

    if not args.no_scrape:
        print("== Шаг 1: скрейпинг сайта фонда ==")
        scrape()

    if args.only_scrape:
        print("Готово (только скрейпинг).")
        return

    print("\n== Шаг 2: загрузка локальных файлов ==")
    load_files()

    print("\n== Шаг 3: построение индекса ==")
    build_index()


if __name__ == "__main__":
    main()
