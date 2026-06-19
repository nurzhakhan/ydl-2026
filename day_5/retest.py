"""Прицельный ре-тест после фикса №1 (умный follow-up).

Проверяем: (1) починился ли главный слом, (2) не сломалась ли регрессия
(настоящие follow-up должны по-прежнему тянуть контекст), (3) ищем новые сломы
на переключениях тем.

Запуск:  .venv/bin/python retest.py
"""
from src.bot.main import is_followup
from src.rag.retriever import Retriever, format_context
from src.llm.client import chat
from src.llm.prompts import SYSTEM_PROMPT, build_user_prompt

retriever = Retriever()


def answer(question, history, lang=None, role=None):
    prev_user = [m["content"] for m in history if m["role"] == "user"][-2:]
    used_ctx = bool(prev_user and is_followup(question))
    rq = "\n".join([*prev_user, question]) if used_ctx else question
    chunks = retriever.retrieve(rq)
    ans = chat(
        SYSTEM_PROMPT,
        build_user_prompt(question, format_context(chunks), preferred_lang=lang, role=role),
        history,
    )
    return ans, chunks, used_ctx


STORIES = [
    ("R1 ФИКС: Data Lab(kz) -> миссия(en)  [был слом]", [
        "Yessenov Data Lab дегеніміз не?",
        "What is the mission of the foundation?",
    ]),
    ("R2 РЕГРЕССИЯ: англ.программа -> там сроки -> могу податься", [
        "Расскажи про программу английского языка",
        "А какие там сроки?",
        "Могу ли я сейчас податься?",
    ]),
    ("R3 переключение(ru): Data Lab -> кто основал фонд?", [
        "Расскажи про Yessenov Data Lab",
        "А кто основал фонд?",
    ]),
    ("R4 переключение: Орлеу -> гранты для абитуриентов?", [
        "Расскажи про программу Орлеу",
        "Какие гранты есть для абитуриентов?",
    ]),
    ("R5 переключение(en): стипендия -> what programs?", [
        "Расскажи про стипендию Есенова",
        "What programs does the foundation have?",
    ]),
    ("R6 follow-up после смены темы: Орлеу->Data Lab->сроки", [
        "Расскажи про программу Орлеу",
        "А теперь расскажи про Yessenov Data Lab",
        "Какие там сроки?",
    ]),
]


def run():
    for title, turns in STORIES:
        print("\n" + "=" * 78)
        print("ИСТОРИЯ:", title)
        print("=" * 78)
        history = []
        for q in turns:
            try:
                ans, chunks, used_ctx = answer(q, history)
            except Exception as exc:  # noqa: BLE001
                print(f"\n  ❌ Q: {q}\n  ❌ ИСКЛЮЧЕНИЕ: {exc!r}")
                continue
            top = chunks[0].source[:58] if chunks else "—(пусто)"
            flag = "ctx+история" if used_ctx else "только вопрос"
            print(f"\n  Q: {q}   [{flag}]")
            print(f"  [top: {top}]")
            print(f"  A: {ans[:420]}")
            history += [
                {"role": "user", "content": q},
                {"role": "assistant", "content": ans[:1000]},
            ]


if __name__ == "__main__":
    run()
    print("\n=== РЕ-ТЕСТ ЗАВЕРШЁН ===")
