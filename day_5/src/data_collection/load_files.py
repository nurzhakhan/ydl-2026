"""Загрузчик локальных файлов из data/raw_docs/.

Поддерживает .txt, .md (нативно), а также .pdf и .docx
(если установлены pypdf и python-docx — см. requirements.txt).
Результат пишется в data/knowledge/file_docs.jsonl.

Запуск отдельно:  python -m src.data_collection.load_files
"""
import json
from pathlib import Path

from src.config import RAW_DOCS_DIR, KNOWLEDGE_DIR, settings

FILE_DOCS_PATH = KNOWLEDGE_DIR / "file_docs.jsonl"
SUPPORTED = {".txt", ".md", ".pdf", ".docx"}


def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        print(f"  ! пропускаю {path.name}: установи pypdf (pip install pypdf)")
        return ""
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx(path: Path) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        print(f"  ! пропускаю {path.name}: установи python-docx (pip install python-docx)")
        return ""
    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs)


_READERS = {".txt": _read_txt, ".md": _read_txt, ".pdf": _read_pdf, ".docx": _read_docx}


def load_files() -> int:
    """Читает все поддерживаемые файлы из raw_docs. Возвращает число документов."""
    files = [p for p in RAW_DOCS_DIR.rglob("*") if p.suffix.lower() in SUPPORTED]
    if not files:
        print(f"В {RAW_DOCS_DIR} нет файлов ({', '.join(sorted(SUPPORTED))}). Пропускаю.")
        # пишем пустой файл, чтобы ingest не падал
        FILE_DOCS_PATH.write_text("", encoding="utf-8")
        return 0

    docs: list[dict] = []
    for path in files:
        reader = _READERS[path.suffix.lower()]
        text = (reader(path) or "").strip()
        if len(text) < 50:
            print(f"  ! {path.name}: пусто или не прочиталось, пропуск")
            continue
        docs.append(
            {
                "source": f"file://{path.name}",
                "title": path.stem,
                "lang": "ru",  # язык исходных файлов считаем русским
                "text": text,
                "origin": "file",
            }
        )
        print(f"  + {path.name} ({len(text)} символов)")

    # Кросс-язык: переводим ручную базу на нужные языки (RU/KZ/EN).
    if settings.manual_multilingual and docs:
        from src.data_collection.translate import expand_multilingual

        print("Перевожу ручную базу для кросс-языкового поиска...")
        docs = expand_multilingual(docs, settings.manual_languages)

    with open(FILE_DOCS_PATH, "w", encoding="utf-8") as out:
        for doc in docs:
            out.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"Готово. Записей ручной базы (с переводами): {len(docs)} -> {FILE_DOCS_PATH}")
    return len(docs)


if __name__ == "__main__":
    load_files()
