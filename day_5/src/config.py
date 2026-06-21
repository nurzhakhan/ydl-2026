"""Центральная конфигурация проекта.

Все ключи и настройки читаются из переменных окружения (файл .env).
Скопируй .env.example в .env и впиши свои значения.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Грузим .env из корня day_5 (на уровень выше папки src)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Пути к данным
DATA_DIR = BASE_DIR / "data"
RAW_DOCS_DIR = DATA_DIR / "raw_docs"      # сюда кладёшь свои файлы (txt/md/pdf/docx)
KNOWLEDGE_DIR = DATA_DIR / "knowledge"    # сюда падают собранные/обработанные тексты
INDEX_DIR = DATA_DIR / "index"            # сюда сохраняется векторный индекс

for _d in (RAW_DOCS_DIR, KNOWLEDGE_DIR, INDEX_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _get(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@dataclass
class Settings:
    # --- Telegram ---
    telegram_token: str = _get("TELEGRAM_BOT_TOKEN")

    # --- LLM (Gemma), OpenAI-совместимый эндпоинт ---
    # По умолчанию настроено под Google AI Studio (Gemma).
    # Можно переключить на OpenRouter/vLLM, поменяв LLM_BASE_URL и LLM_MODEL.
    llm_api_key: str = _get("LLM_API_KEY")
    llm_base_url: str = _get(
        "LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    llm_model: str = _get("LLM_MODEL", "gemma-3-27b-it")
    llm_temperature: float = float(_get("LLM_TEMPERATURE", "0.2"))
    llm_max_tokens: int = int(_get("LLM_MAX_TOKENS", "1024"))
    # Gemma не всегда принимает роль "system" — тогда сольём инструкцию в user.
    system_as_user: bool = _get("SYSTEM_AS_USER", "false").lower() == "true"

    # --- Embeddings ---
    emb_api_key: str = _get("EMBEDDINGS_API_KEY")
    emb_base_url: str = _get(
        "EMBEDDINGS_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    emb_model: str = _get("EMBEDDINGS_MODEL", "text-embedding-004")
    emb_batch_size: int = int(_get("EMBEDDINGS_BATCH_SIZE", "32"))

    # --- RAG ---
    chunk_size: int = int(_get("CHUNK_SIZE", "1200"))
    chunk_overlap: int = int(_get("CHUNK_OVERLAP", "200"))
    top_k: int = int(_get("TOP_K", "5"))
    min_score: float = float(_get("MIN_SCORE", "0.25"))
    # Бонус за свежесть: насколько новые страницы (по году в URL/заголовке)
    # поднимаются над старыми. 0 = выключить, 0.08 = умеренно.
    recency_weight: float = float(_get("RECENCY_WEIGHT", "0.08"))
    # Если в ВОПРОСЕ указан конкретный год (напр. «Data Lab 2019») — бонус
    # за свежесть отключается, а страницы этого года поднимаются вверх.
    year_match_boost: float = float(_get("YEAR_MATCH_BOOST", "0.15"))
    # Приоритет ручной базы (data/raw_docs): твои файлы идут отдельным
    # приоритетным тиром — бот смотрит сначала на них. Фрагмент попадает в
    # ответ, если совпадает с вопросом по словам (лексический фильтр) и его
    # близость не ниже manual_min_score. manual_reserve — сколько верхних
    # мест резервируется под ручную базу.
    manual_min_score: float = float(_get("MANUAL_MIN_SCORE", "0.08"))
    manual_reserve: int = int(_get("MANUAL_RESERVE", "1"))
    # Многоязычная индексация ручной базы: переводим твои файлы на эти языки,
    # чтобы вопрос на любом из них находил нужную версию (кросс-язык).
    manual_multilingual: bool = _get("MANUAL_MULTILINGUAL", "true").lower() == "true"
    manual_languages: tuple[str, ...] = tuple(
        s.strip()
        for s in _get("MANUAL_LANGUAGES", "ru,kk,en").split(",")
        if s.strip()
    )

    # --- Скрейпер сайта фонда ---
    site_base_url: str = _get("SITE_BASE_URL", "https://yessenovfoundation.org")
    scrape_max_pages: int = int(_get("SCRAPE_MAX_PAGES", "600"))
    scrape_timeout: int = int(_get("SCRAPE_TIMEOUT", "30"))
    # Берём в базу знаний ТОЛЬКО эти разделы сайта (allowlist по первому
    # сегменту пути, без языкового префикса). Раздел новостей и статьи
    # (корневые слаги, /category/) сюда не входят — они путают бота.
    site_include_sections: tuple[str, ...] = tuple(
        s.strip()
        for s in _get("SITE_INCLUDE_SECTIONS", "about-us,sh-esenov").split(",")
        if s.strip()
    )
    # Дополнительно ИСКЛЮЧАЕМ страницы, чей путь содержит любую из этих
    # подстрок (работает поверх allowlist, для всех языковых версий).
    site_exclude_paths: tuple[str, ...] = tuple(
        s.strip()
        for s in _get("SITE_EXCLUDE_PATHS", "").split(",")
        if s.strip()
    )


settings = Settings()
