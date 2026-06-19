"""Клиент эмбеддингов (OpenAI-совместимый).

Работает с Google AI Studio (text-embedding-004), OpenAI, и любым
OpenAI-совместимым провайдером — настраивается в .env.
"""
import time

from openai import APIConnectionError, InternalServerError, OpenAI, RateLimitError

from src.config import settings

_RETRYABLE = (InternalServerError, APIConnectionError, RateLimitError)
_MAX_RETRIES = 4
_RETRY_DELAY = 3.0

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.emb_api_key:
            raise RuntimeError(
                "Не задан EMBEDDINGS_API_KEY в .env — добавь ключ для эмбеддингов."
            )
        _client = OpenAI(api_key=settings.emb_api_key, base_url=settings.emb_base_url)
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Возвращает векторы для списка текстов (батчами)."""
    client = _get_client()
    vectors: list[list[float]] = []
    batch = settings.emb_batch_size
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = client.embeddings.create(model=settings.emb_model, input=chunk)
                break
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
        else:
            raise last_exc  # type: ignore[misc]
        # сортировка по index на всякий случай
        items = sorted(resp.data, key=lambda d: d.index)
        vectors.extend(item.embedding for item in items)
    return vectors


def embed_query(text: str) -> list[float]:
    """Вектор одного запроса."""
    return embed_texts([text])[0]
