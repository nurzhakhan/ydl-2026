"""Разбивка длинных текстов на чанки (фрагменты) для RAG.

Режем по абзацам, набирая куски примерно по chunk_size символов
с перекрытием chunk_overlap, чтобы не терять контекст на стыках.
"""
import re

from src.config import settings


def clean_text(text: str) -> str:
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Возвращает список чанков. Старается не рвать абзацы."""
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Абзац влезает в текущий чанк
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}".strip()
            continue
        # Не влезает: закрываем текущий чанк
        if current:
            chunks.append(current)
        # Очень длинный абзац режем жёстко с перекрытием
        if len(para) > chunk_size:
            step = max(1, chunk_size - overlap)
            for i in range(0, len(para), step):
                chunks.append(para[i : i + chunk_size])
            current = ""
        else:
            current = para

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]
