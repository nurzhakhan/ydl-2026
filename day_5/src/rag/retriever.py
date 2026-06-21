"""Ретривер: по вопросу пользователя достаёт релевантные фрагменты базы знаний.

Кроме косинусной близости учитывает СВЕЖЕСТЬ: если в URL/заголовке есть год
(например, ydl-2026), более новые страницы получают бонус к рангу — чтобы
сначала шла актуальная информация, а не архив прошлых лет.
"""
import datetime
import re
from dataclasses import dataclass

from src.config import settings
from src.rag.embeddings import embed_query
from src.rag.vector_store import VectorStore

_YEAR_RE = re.compile(r"20[1-3]\d")
_BASE_YEAR = 2013  # год основания фонда — нижняя граница шкалы свежести
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _extract_year(*texts: str) -> int | None:
    """Максимальный правдоподобный год из URL/заголовка (или None)."""
    years = [
        int(y)
        for t in texts
        for y in _YEAR_RE.findall(t or "")
        if _BASE_YEAR <= int(y) <= 2035
    ]
    return max(years) if years else None


def _stems(text: str) -> set[str]:
    """Грубые «стемы»: первые 4 символа значимых слов (len>=4), в нижнем регистре.

    Снимает часть морфологии (миссия/миссии -> 'мисс', фонд/фонда -> 'фонд'),
    чтобы лексически сопоставлять вопрос и фрагмент без полноценного стеммера.
    """
    return {w.lower()[:4] for w in _WORD_RE.findall(text or "") if len(w) >= 4}


def _lexical_overlap(question: str, text: str) -> int:
    """Сколько значимых слов вопроса встречается во фрагменте (по стемам)."""
    return len(_stems(question) & _stems(text))


@dataclass
class RetrievedChunk:
    text: str
    source: str
    title: str
    lang: str
    score: float  # исходная косинусная близость (без бонусов)
    year: int | None = None
    origin: str = "site"  # 'file' = твой файл, 'site' = авто-скрейп


class Retriever:
    """Загружает индекс один раз и обслуживает запросы."""

    def __init__(self) -> None:
        self.store = VectorStore.load()

    @property
    def is_empty(self) -> bool:
        return len(self.store) == 0

    def retrieve(self, question: str, top_k: int | None = None) -> list[RetrievedChunk]:
        if self.is_empty:
            return []
        top_k = top_k or settings.top_k
        query_vec = embed_query(question)
        # Ранжируем ВСЕ фрагменты по близости (store отсортирует по убыванию).
        all_hits = self.store.search(query_vec, top_k=len(self.store))

        cur_year = datetime.date.today().year
        span = max(1, cur_year - _BASE_YEAR)

        def to_chunk(meta: dict, score: float) -> RetrievedChunk:
            return RetrievedChunk(
                text=meta.get("text", ""),
                source=meta.get("source", ""),
                title=meta.get("title", ""),
                lang=meta.get("lang", "ru"),
                score=score,
                year=_extract_year(meta.get("source", ""), meta.get("title", "")),
                origin=meta.get("origin", "site"),
            )

        # --- Тир 1: ручная база (приоритет) ---
        # Берём фрагменты твоих файлов, которые лексически совпадают с вопросом
        # и проходят мягкий порог близости. Они идут ПЕРВЫМИ в контексте.
        manual: list[RetrievedChunk] = []
        seen_files: set[str] = set()
        for meta, score in all_hits:
            if meta.get("origin") != "file":
                continue
            if score < settings.manual_min_score:
                continue
            if _lexical_overlap(question, meta.get("text", "")) == 0:
                continue
            src = meta.get("source", "")
            if src in seen_files:  # тот же файл в другом языке уже взят — пропускаем
                continue
            seen_files.add(src)
            manual.append(to_chunk(meta, score))
            if len(manual) >= settings.manual_reserve:
                break

        # Если в вопросе указан конкретный год — приоритет ему, а не свежести.
        query_years = {
            int(y)
            for y in _YEAR_RE.findall(question)
            if _BASE_YEAR <= int(y) <= 2035
        }

        # --- Тир 2: сайт (приоритет запрошенного года либо свежести) ---
        site_scored: list[tuple[RetrievedChunk, float]] = []
        for meta, score in all_hits:
            if meta.get("origin") == "file":
                continue
            if score < settings.min_score:
                continue
            chunk = to_chunk(meta, score)
            if query_years:
                # Спросили конкретный год -> поднимаем совпадающий, без recency.
                boost = settings.year_match_boost if chunk.year in query_years else 0.0
            elif chunk.year is not None:
                boost = settings.recency_weight * (min(chunk.year, cur_year) - _BASE_YEAR) / span
            else:
                boost = 0.0
            site_scored.append((chunk, score + boost))
        site_scored.sort(key=lambda x: x[1], reverse=True)
        site = [chunk for chunk, _ in site_scored]

        # Ручная база впереди, затем сайт; общий размер — top_k.
        return (manual + site)[:top_k]


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Склеивает фрагменты в нумерованный контекст для промпта."""
    blocks = []
    for i, ch in enumerate(chunks, 1):
        header = f"[Источник {i}] {ch.title}".strip()
        blocks.append(f"{header}\nURL: {ch.source}\n{ch.text}")
    return "\n\n---\n\n".join(blocks)


def unique_sources(chunks: list[RetrievedChunk], limit: int = 3) -> list[tuple[str, str]]:
    """Уникальные источники (title, url) для показа под ответом."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for ch in chunks:
        if ch.source.startswith("file://"):
            continue  # локальные файлы не даём как ссылку
        if ch.source in seen:
            continue
        seen.add(ch.source)
        out.append((ch.title or ch.source, ch.source))
        if len(out) >= limit:
            break
    return out
