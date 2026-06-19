"""Клиент LLM (Gemma) через OpenAI-совместимый эндпоинт.

По умолчанию — Google AI Studio (gemma-3-27b-it). Настраивается в .env.
Если провайдер не принимает роль "system" (бывает у Gemma), включи
SYSTEM_AS_USER=true — инструкция уйдёт в начало пользовательского сообщения.
"""
import time

from openai import APIConnectionError, InternalServerError, OpenAI, RateLimitError

from src.config import settings

# Эндпоинт alem.ai иногда отдаёт временные 500/connection error — повторяем.
_RETRYABLE = (InternalServerError, APIConnectionError, RateLimitError)
_MAX_RETRIES = 4
_RETRY_DELAY = 3.0  # секунды между попытками

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.llm_api_key:
            raise RuntimeError("Не задан LLM_API_KEY в .env — добавь ключ Gemma.")
        _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client


def _create(messages: list[dict], temp: float):
    """Запрос с автоповтором на временные ошибки сервера."""
    client = _get_client()
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                temperature=temp,
                max_tokens=settings.llm_max_tokens,
            )
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY)
    raise last_exc  # type: ignore[misc]


def _build_messages(
    system_prompt: str, history: list[dict], user_prompt: str, as_user: bool
) -> list[dict]:
    """Собирает список сообщений: system + история диалога + текущий вопрос."""
    convo = list(history) + [{"role": "user", "content": user_prompt}]
    if as_user:
        # Провайдер не принимает role=system — вшиваем инструкцию в первое
        # пользовательское сообщение.
        if convo and convo[0]["role"] == "user":
            convo = [
                {"role": "user", "content": f"{system_prompt}\n\n{convo[0]['content']}"}
            ] + convo[1:]
        else:
            convo = [{"role": "user", "content": system_prompt}] + convo
        return convo
    return [{"role": "system", "content": system_prompt}] + convo


def chat(
    system_prompt: str,
    user_prompt: str,
    history: list[dict] | None = None,
    temperature: float | None = None,
) -> str:
    """Запрос к модели с учётом истории диалога. Возвращает текст ответа.

    history — список сообщений вида {"role": "user"|"assistant", "content": ...}
    (предыдущие реплики, без текущего вопроса).
    """
    temp = settings.llm_temperature if temperature is None else temperature
    history = history or []

    try:
        messages = _build_messages(
            system_prompt, history, user_prompt, settings.system_as_user
        )
        resp = _create(messages, temp)
    except Exception as exc:  # noqa: BLE001
        # Фолбэк: некоторые эндпоинты Gemma не принимают role=system
        if "system" in str(exc).lower() and not settings.system_as_user:
            messages = _build_messages(system_prompt, history, user_prompt, True)
            resp = _create(messages, temp)
        else:
            raise

    return (resp.choices[0].message.content or "").strip()
