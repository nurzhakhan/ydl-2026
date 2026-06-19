"""Перевод ручной базы на несколько языков для кросс-языкового поиска.

Каждый файл из data/raw_docs индексируется на RU/KZ/EN, чтобы вопрос на любом
из этих языков лексически и семантически совпадал с нужной версией, а LLM
получал контекст на языке вопроса. Переводы кэшируются (LLM нестабилен/платный).
"""
import hashlib
import json

from src.config import KNOWLEDGE_DIR, settings
from src.llm.client import chat

CACHE_PATH = KNOWLEDGE_DIR / "translation_cache.json"

_LANG_NAMES = {"ru": "русский", "kk": "казахский", "en": "английский (English)"}


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")


def _key(text: str, lang: str) -> str:
    return hashlib.md5(f"{lang}|{text}".encode("utf-8")).hexdigest()


def translate(text: str, target_lang: str, cache: dict) -> str:
    """Переводит текст на target_lang. Возвращает '' при неудаче."""
    k = _key(text, target_lang)
    if k in cache:
        return cache[k]
    lang_name = _LANG_NAMES.get(target_lang, target_lang)
    system = (
        f"Ты профессиональный переводчик. Переведи текст на {lang_name} язык. "
        f"Сохрани смысл, имена собственные, числа и Markdown-разметку. "
        f"Выведи ТОЛЬКО перевод, без пояснений и кавычек."
    )
    try:
        result = chat(system, text).strip()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! перевод на {target_lang} не удался: {exc}")
        return ""
    if result:
        cache[k] = result
    return result


def expand_multilingual(docs: list[dict], languages: tuple[str, ...]) -> list[dict]:
    """Расширяет список документов переводами на заданные языки.

    Оригинал сохраняется как есть; для остальных языков создаётся копия с
    переведённым текстом и проставленным lang. Источник (source) не меняется.
    """
    cache = _load_cache()
    out: list[dict] = []
    for doc in docs:
        src_lang = doc.get("lang", "ru")
        out.append(doc)  # оригинал
        for lang in languages:
            if lang == src_lang:
                continue
            translated = translate(doc.get("text", ""), lang, cache)
            if not translated:
                continue
            copy = dict(doc)
            copy["text"] = translated
            copy["lang"] = lang
            out.append(copy)
            print(f"  + перевод {doc.get('title', '')} -> {lang}")
    _save_cache(cache)
    return out
