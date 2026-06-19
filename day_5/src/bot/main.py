"""Телеграм-бот фонда (aiogram v3).

Онбординг:
  /start
    -> выбор языка (RU/KZ/EN)
    -> краткое описание фонда (миссия, цель)
    -> выбор роли (абитуриент / выпускник / партнёр)
    -> роль-специфичная подсказка, чем бот помогает
    -> пользователь задаёт вопрос.

Ответ строится через RAG (поиск по базе) + Gemma, с учётом языка и роли.

Запуск:  python -m src.bot.main
"""
import asyncio
import html as html_lib
import logging
import re

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from src.config import settings
from src.llm.client import chat
from src.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from src.rag.retriever import Retriever, format_context, unique_sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("yessenov-bot")

TELEGRAM_LIMIT = 4096

# Состояние пользователя (в памяти)
user_lang: dict[int, str] = {}   # user_id -> 'ru' | 'kk' | 'en'
user_role: dict[int, str] = {}   # user_id -> 'applicant' | 'alumni' | 'partner'
# История диалога: user_id -> [{"role": "user"|"assistant", "content": ...}, ...]
user_history: dict[int, list[dict]] = {}

MAX_HISTORY_MESSAGES = 6   # хранить последние 3 обмена (вопрос+ответ)
HISTORY_ANSWER_CAP = 1000  # обрезка длинных ответов в истории (экономим токены)

LANGS = ("ru", "kk", "en")
ROLES = ("applicant", "alumni", "partner")

# --- Шаг 1: выбор языка ---
LANG_PROMPT = "🌐 Выберите язык / Тілді таңдаңыз / Choose your language:"

# --- Шаг 2: описание фонда + приглашение выбрать роль ---
INTRO = {
    "ru": (
        "🏛 <b>Фонд Шахмардана Есенова</b>\n\n"
        "Научно-образовательный фонд имени академика Шахмардана Есенова — "
        "частный благотворительный фонд (основан в 2013 году). Развивает "
        "интеллектуальный потенциал Казахстана и поддерживает талантливую "
        "молодёжь в науке, технологиях и инженерии.\n\n"
        "🎯 <b>Миссия и цель:</b> помогать талантливым казахстанцам получать "
        "образование и расти, чтобы они меняли страну к лучшему.\n\n"
        "👤 Подскажите, кто вы — так я помогу точнее:"
    ),
    "kk": (
        "🏛 <b>Шахмардан Есенов қоры</b>\n\n"
        "Академик Шахмардан Есенов атындағы ғылыми-білім беру қоры — жеке "
        "қайырымдылық қоры (2013 жылы құрылған). Қазақстанның зияткерлік "
        "әлеуетін дамытады әрі ғылым, технология мен инженерия саласындағы "
        "дарынды жастарды қолдайды.\n\n"
        "🎯 <b>Миссиясы мен мақсаты:</b> дарынды қазақстандықтарға білім алуға "
        "және дамуға көмектесу.\n\n"
        "👤 Айтыңызшы, сіз кімсіз — нақтырақ көмектесейін:"
    ),
    "en": (
        "🏛 <b>Shakhmardan Yessenov Foundation</b>\n\n"
        "The Shakhmardan Yessenov Science and Education Foundation is a private "
        "charitable foundation (established in 2013). It develops Kazakhstan's "
        "intellectual potential and supports talented youth in science, "
        "technology and engineering.\n\n"
        "🎯 <b>Mission &amp; goal:</b> to help talented Kazakhstanis access "
        "education and grow so they can change the country for the better.\n\n"
        "👤 Tell me who you are so I can help you better:"
    ),
}

# Подписи кнопок ролей
ROLE_LABELS = {
    "ru": {
        "applicant": "🎓 Абитуриент / студент / молодой учёный",
        "alumni": "🏅 Грантополучатель / выпускник",
        "partner": "🤝 Спонсор / партнёр",
    },
    "kk": {
        "applicant": "🎓 Талапкер / студент / жас ғалым",
        "alumni": "🏅 Грант иегері / түлек",
        "partner": "🤝 Демеуші / серіктес",
    },
    "en": {
        "applicant": "🎓 Applicant / student / young scientist",
        "alumni": "🏅 Grant recipient / alumnus",
        "partner": "🤝 Sponsor / partner",
    },
}

# --- Шаг 3: чем бот помогает выбранной роли ---
ROLE_INTRO = {
    "applicant": {
        "ru": (
            "🎓 <b>Для абитуриентов, студентов и молодых учёных</b>\n\n"
            "Я помогу вам:\n"
            "• подобрать гранты и стипендии\n"
            "• узнать условия участия и требования\n"
            "• уточнить сроки подачи заявок\n"
            "• понять, как проходит отбор\n\n"
            "Например, спросите:\n"
            "• «Какие гранты есть для студентов?»\n"
            "• «Условия стипендии Есенова»\n"
            "• «Сроки Yessenov Data Lab 2026»\n\n"
            "✍️ Напишите свой вопрос 👇"
        ),
        "kk": (
            "🎓 <b>Талапкерлер, студенттер және жас ғалымдарға</b>\n\n"
            "Мен көмектесемін:\n"
            "• гранттар мен стипендияларды таңдау\n"
            "• қатысу шарттары мен талаптарын білу\n"
            "• өтінім беру мерзімдерін нақтылау\n"
            "• іріктеу қалай өтетінін түсіну\n\n"
            "Мысалы, сұраңыз:\n"
            "• «Студенттерге қандай гранттар бар?»\n"
            "• «Есенов стипендиясының шарттары»\n"
            "• «Yessenov Data Lab 2026 мерзімдері»\n\n"
            "✍️ Сұрағыңызды жазыңыз 👇"
        ),
        "en": (
            "🎓 <b>For applicants, students and young scientists</b>\n\n"
            "I can help you:\n"
            "• find grants and scholarships\n"
            "• learn eligibility and requirements\n"
            "• check application deadlines\n"
            "• understand the selection process\n\n"
            "For example, ask:\n"
            "• \"What grants are available for students?\"\n"
            "• \"Yessenov Scholarship conditions\"\n"
            "• \"Yessenov Data Lab 2026 dates\"\n\n"
            "✍️ Type your question 👇"
        ),
    },
    "alumni": {
        "ru": (
            "🏅 <b>Для грантополучателей и выпускников (alumni)</b>\n\n"
            "Я помогу вам:\n"
            "• узнать о сообществе выпускников и мероприятиях\n"
            "• найти действующие возможности и программы\n"
            "• уточнить условия текущих грантов\n"
            "• узнать истории успеха выпускников\n\n"
            "Например:\n"
            "• «Какие мероприятия фонд проводит для выпускников?»\n"
            "• «Истории успеха грантополучателей»\n\n"
            "✍️ Напишите свой вопрос 👇"
        ),
        "kk": (
            "🏅 <b>Грант иегерлері мен түлектерге (alumni)</b>\n\n"
            "Мен көмектесемін:\n"
            "• түлектер қауымдастығы мен іс-шаралар туралы білу\n"
            "• қолжетімді мүмкіндіктер мен бағдарламаларды табу\n"
            "• ағымдағы гранттардың шарттарын нақтылау\n"
            "• түлектердің табыс тарихтарын білу\n\n"
            "Мысалы:\n"
            "• «Қор түлектерге қандай іс-шаралар өткізеді?»\n\n"
            "✍️ Сұрағыңызды жазыңыз 👇"
        ),
        "en": (
            "🏅 <b>For grant recipients and alumni</b>\n\n"
            "I can help you:\n"
            "• learn about the alumni community and events\n"
            "• find current opportunities and programs\n"
            "• clarify conditions of ongoing grants\n"
            "• discover alumni success stories\n\n"
            "For example:\n"
            "• \"What events does the foundation hold for alumni?\"\n\n"
            "✍️ Type your question 👇"
        ),
    },
    "partner": {
        "ru": (
            "🤝 <b>Для спонсоров и партнёров</b>\n\n"
            "Я помогу вам:\n"
            "• узнать о миссии и программах фонда\n"
            "• понять результаты и охват программ\n"
            "• узнать, как поддержать фонд или стать партнёром\n\n"
            "Например:\n"
            "• «Каких результатов достиг фонд?»\n"
            "• «Как стать партнёром фонда?»\n\n"
            "✍️ Напишите свой вопрос 👇"
        ),
        "kk": (
            "🤝 <b>Демеушілер мен серіктестерге</b>\n\n"
            "Мен көмектесемін:\n"
            "• қордың миссиясы мен бағдарламалары туралы білу\n"
            "• бағдарламалардың нәтижелері мен ауқымын түсіну\n"
            "• қорды қалай қолдауға не серіктес болуға болатынын білу\n\n"
            "Мысалы:\n"
            "• «Қор қандай нәтижелерге қол жеткізді?»\n\n"
            "✍️ Сұрағыңызды жазыңыз 👇"
        ),
        "en": (
            "🤝 <b>For sponsors and partners</b>\n\n"
            "I can help you:\n"
            "• learn about the foundation's mission and programs\n"
            "• understand program results and reach\n"
            "• find out how to support the foundation or become a partner\n\n"
            "For example:\n"
            "• \"What results has the foundation achieved?\"\n"
            "• \"How can I become a partner?\"\n\n"
            "✍️ Type your question 👇"
        ),
    },
}

HELP = {
    "ru": (
        "ℹ️ Я отвечаю на вопросы о Фонде Есенова по официальным материалам сайта.\n\n"
        "/start — выбрать язык и роль заново\n"
        "/reset — очистить контекст диалога\n/help — эта справка\n\n"
        "Сайт: yessenovfoundation.org"
    ),
    "kk": (
        "ℹ️ Мен Есенов қоры туралы сұрақтарға сайттың ресми материалдары "
        "бойынша жауап беремін.\n\n"
        "/start — тіл мен рөлді қайта таңдау\n"
        "/reset — диалог контекстін тазарту\n/help — осы анықтама\n\n"
        "Сайт: yessenovfoundation.org"
    ),
    "en": (
        "ℹ️ I answer questions about the Yessenov Foundation based on the "
        "official website materials.\n\n"
        "/start — choose language and role again\n"
        "/reset — clear conversation context\n/help — this help\n\n"
        "Website: yessenovfoundation.org"
    ),
}

SOURCES_LABEL = {"ru": "📎 Источники:", "kk": "📎 Дереккөздер:", "en": "📎 Sources:"}

RESET_MSG = {
    "ru": "🧹 Контекст диалога очищен. Можете задать новый вопрос с чистого листа.",
    "kk": "🧹 Диалог контексті тазартылды. Жаңа сұрақ қоя аласыз.",
    "en": "🧹 Conversation context cleared. You can start a fresh question.",
}

# Кнопка «Настройки» у поля ввода (reply-клавиатура) -> по нажатию выбор языка
SETTINGS_BTN = {"ru": "⚙️ Настройки", "kk": "⚙️ Баптаулар", "en": "⚙️ Settings"}
SETTINGS_VALUES = set(SETTINGS_BTN.values())

POPULAR_LABEL = {
    "ru": "💡 Популярные вопросы — нажмите или напишите свой:",
    "kk": "💡 Танымал сұрақтар — басыңыз немесе өзіңіздікін жазыңыз:",
    "en": "💡 Popular questions — tap one or type your own:",
}

# Подсказки-вопросы под каждой ролью: (надпись на кнопке, полный вопрос).
ROLE_QUESTIONS = {
    "applicant": {
        "ru": [
            ("📚 Гранты для студентов", "Какие гранты и стипендии есть для студентов и абитуриентов?"),
            ("🎓 Стипендия Есенова", "Какие условия и размер стипендии имени Есенова?"),
            ("🗓 Сроки Data Lab 2026", "Какие сроки подачи заявок на Yessenov Data Lab 2026?"),
        ],
        "kk": [
            ("📚 Студенттерге гранттар", "Студенттер мен талапкерлерге қандай гранттар мен стипендиялар бар?"),
            ("🎓 Есенов стипендиясы", "Есенов атындағы стипендияның шарттары мен мөлшері қандай?"),
            ("🗓 Data Lab 2026 мерзімі", "Yessenov Data Lab 2026 өтінім беру мерзімдері қандай?"),
        ],
        "en": [
            ("📚 Grants for students", "What grants and scholarships are available for students and applicants?"),
            ("🎓 Yessenov Scholarship", "What are the conditions and amount of the Yessenov Scholarship?"),
            ("🗓 Data Lab 2026 deadlines", "What are the application deadlines for Yessenov Data Lab 2026?"),
        ],
    },
    "alumni": {
        "ru": [
            ("🤝 Сообщество выпускников", "Что такое сообщество выпускников фонда и как туда попасть?"),
            ("📅 Мероприятия для alumni", "Какие мероприятия фонд проводит для выпускников?"),
            ("🌟 Истории успеха", "Расскажи истории успеха грантополучателей фонда"),
        ],
        "kk": [
            ("🤝 Түлектер қауымдастығы", "Қордың түлектер қауымдастығы дегеніміз не және оған қалай қосылуға болады?"),
            ("📅 Түлектерге іс-шаралар", "Қор түлектер үшін қандай іс-шаралар өткізеді?"),
            ("🌟 Табыс тарихтары", "Қор грант иегерлерінің табыс тарихтарын айтып бер"),
        ],
        "en": [
            ("🤝 Alumni community", "What is the foundation's alumni community and how can I join it?"),
            ("📅 Events for alumni", "What events does the foundation hold for alumni?"),
            ("🌟 Success stories", "Tell me success stories of the foundation's grant recipients"),
        ],
    },
    "partner": {
        "ru": [
            ("🎯 Миссия фонда", "Какая миссия и цель фонда?"),
            ("📊 Результаты фонда", "Каких результатов и охвата достиг фонд?"),
            ("🤝 Стать партнёром", "Как поддержать фонд или стать партнёром?"),
        ],
        "kk": [
            ("🎯 Қор миссиясы", "Қордың миссиясы мен мақсаты қандай?"),
            ("📊 Қор нәтижелері", "Қор қандай нәтижелер мен ауқымға қол жеткізді?"),
            ("🤝 Серіктес болу", "Қорды қалай қолдауға немесе серіктес болуға болады?"),
        ],
        "en": [
            ("🎯 Foundation mission", "What is the mission and goal of the foundation?"),
            ("📊 Foundation results", "What results and reach has the foundation achieved?"),
            ("🤝 Become a partner", "How can I support the foundation or become a partner?"),
        ],
    },
}

# Ретривер грузим один раз при старте
retriever: Retriever | None = None
dp = Dispatcher()


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang:kk"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            ]
        ]
    )


def role_keyboard(lang: str) -> InlineKeyboardMarkup:
    labels = ROLE_LABELS.get(lang, ROLE_LABELS["ru"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=labels[role], callback_data=f"role:{role}")]
            for role in ROLES
        ]
    )


def settings_reply_kb(lang: str) -> ReplyKeyboardMarkup:
    """Постоянная кнопка «Настройки» у поля ввода."""
    label = SETTINGS_BTN.get(lang, SETTINGS_BTN["ru"])
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def role_questions_kb(role: str, lang: str) -> InlineKeyboardMarkup:
    """Инлайн-кнопки с типовыми вопросами под выбранную роль."""
    qs = ROLE_QUESTIONS.get(role, {}).get(lang) or ROLE_QUESTIONS.get(role, {}).get("ru", [])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"ask:{role}:{lang}:{i}")]
            for i, (label, _q) in enumerate(qs)
        ]
    )


# Слова-маркеры ссылочного (follow-up) вопроса — он опирается на прошлый контекст.
_REF_MARKERS = {
    "там", "туда", "сейчас", "тогда", "этот", "эта", "это", "эти", "этой",
    "этого", "эту", "его", "её", "ее", "их", "ним", "ней", "нём", "нем",
    "неё", "нее", "он", "она", "они", "тут", "здесь",
    "this", "that", "there", "it", "its", "they", "them",
    "ол", "осы", "сол", "бұл", "оның", "онда", "оған",
}
# Слова, делающие вопрос самодостаточным (своя тема) — историю НЕ подмешиваем.
_TOPIC_MARKERS = (
    "миссия", "миссиясы", "mission", "стипенди", "scholarship", "шәкіртақы",
    "data lab", "дата лаб", "даталаб", "орлеу", "orleu", "өрлеу",
    "английск", "ағылшын", "english", "launch pad", "лаунч", "launchpad",
    "стажиров", "internship", "тағылымдама", "find your way",
    "есеновск", "основа", "негіз", "биограф", "biography",
    "партнёр", "партнер", "спонсор", "sponsor", "founder", "основал",
)


def is_followup(question: str) -> bool:
    """True, если вопрос опирается на предыдущий контекст (его надо дополнить
    историей при поиске). Самодостаточный вопрос со своей темой -> False."""
    q = question.lower()
    if any(kw in q for kw in _TOPIC_MARKERS):
        return False  # есть собственная тема — ищем по самому вопросу
    words = re.findall(r"\w+", q)
    has_ref = any(w in _REF_MARKERS for w in words)
    is_short = len(words) <= 4
    return has_ref or is_short


def md_to_html(text: str) -> str:
    """Конвертирует Markdown от модели в Telegram-HTML.

    Поддержка: **жирный** / __жирный__ -> <b>, заголовки '# ...' -> жирная
    строка, маркеры списков '*'/'-' -> '•'. Спецсимволы HTML экранируются,
    чтобы Telegram корректно распарсил разметку.
    """
    text = html_lib.escape(text, quote=False)  # & < >  (теги добавляем после)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*(.+?)\s*$", r"<b>\1</b>", text)
    text = re.sub(r"(?m)^(\s*)[\*\-]\s+", r"\1• ", text)
    return text


def html_to_plain(text: str) -> str:
    """Фолбэк: убирает HTML-теги и возвращает чистый текст."""
    return html_lib.unescape(re.sub(r"<[^>]+>", "", text))


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Режет длинный ответ на части под лимит Telegram."""
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            parts.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        parts.append(current)
    return parts


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    user_history.pop(message.from_user.id, None)  # новая сессия — чистим историю
    await message.answer(LANG_PROMPT, reply_markup=lang_keyboard())


@dp.callback_query(F.data.startswith("lang:"))
async def on_lang_selected(callback: CallbackQuery) -> None:
    lang = callback.data.split(":", 1)[1]
    if lang not in LANGS:
        lang = "ru"
    user_lang[callback.from_user.id] = lang
    await callback.answer()
    await callback.message.answer(
        INTRO[lang], parse_mode="HTML", reply_markup=role_keyboard(lang)
    )


@dp.callback_query(F.data.startswith("role:"))
async def on_role_selected(callback: CallbackQuery) -> None:
    role = callback.data.split(":", 1)[1]
    if role not in ROLES:
        role = "applicant"
    lang = user_lang.get(callback.from_user.id, "ru")
    user_role[callback.from_user.id] = role
    await callback.answer()
    # Описание роли + постоянная кнопка «Настройки» у поля ввода.
    await callback.message.answer(
        ROLE_INTRO[role][lang], parse_mode="HTML", reply_markup=settings_reply_kb(lang)
    )
    # Кнопки-подсказки с типовыми вопросами для этой роли.
    await callback.message.answer(
        POPULAR_LABEL[lang], reply_markup=role_questions_kb(role, lang)
    )


@dp.message(Command("reset"))
async def on_reset(message: Message) -> None:
    uid = message.from_user.id
    user_history.pop(uid, None)
    lang = user_lang.get(uid, "ru")
    await message.answer(RESET_MSG[lang])


@dp.message(Command("help"))
async def on_help(message: Message) -> None:
    lang = user_lang.get(message.from_user.id, "ru")
    await message.answer(HELP[lang])


async def run_answer(bot: Bot, chat_id: int, uid: int, question: str) -> None:
    """Общая логика ответа на вопрос (из текста или из кнопки-подсказки)."""
    lang = user_lang.get(uid)   # может быть None
    role = user_role.get(uid)   # может быть None
    history = user_history.get(uid, [])
    await bot.send_chat_action(chat_id, ChatAction.TYPING)

    # Контекстный поиск: историю подмешиваем ТОЛЬКО для ссылочных follow-up
    # ("а какие там сроки?"). Самодостаточный вопрос ищем по нему одному.
    prev_user = [m["content"] for m in history if m["role"] == "user"][-2:]
    if prev_user and is_followup(question):
        retrieval_query = "\n".join([*prev_user, question])
    else:
        retrieval_query = question

    try:
        chunks = await asyncio.to_thread(retriever.retrieve, retrieval_query)
        context = format_context(chunks)
        user_prompt = build_user_prompt(question, context, preferred_lang=lang, role=role)
        answer = await asyncio.to_thread(chat, SYSTEM_PROMPT, user_prompt, history)
    except Exception:  # noqa: BLE001
        logger.exception("Ошибка обработки вопроса")
        await bot.send_message(
            chat_id,
            "⚠️ Произошла ошибка при обработке запроса. Попробуйте ещё раз чуть позже.",
        )
        return

    # Сохраняем обмен в историю (ответ обрезаем, чтобы не раздувать токены).
    user_history[uid] = (
        history
        + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer[:HISTORY_ANSWER_CAP]},
        ]
    )[-MAX_HISTORY_MESSAGES:]

    body = md_to_html(answer)
    sources = unique_sources(chunks)
    if sources:
        label = SOURCES_LABEL.get(lang or "ru", SOURCES_LABEL["ru"])
        links = "\n".join(
            f'• <a href="{html_lib.escape(url, quote=True)}">'
            f"{html_lib.escape(title)}</a>"
            for title, url in sources
        )
        body = f"{body}\n\n{label}\n{links}"

    for part in split_message(body):
        try:
            await bot.send_message(
                chat_id, part, parse_mode="HTML", disable_web_page_preview=True
            )
        except Exception:  # noqa: BLE001 — если HTML не распарсился, шлём чистый текст
            await bot.send_message(
                chat_id, html_to_plain(part), disable_web_page_preview=True
            )


@dp.message(F.text.in_(SETTINGS_VALUES))
async def on_settings(message: Message) -> None:
    """Нажатие кнопки «Настройки» -> выбор языка."""
    await message.answer(LANG_PROMPT, reply_markup=lang_keyboard())


@dp.callback_query(F.data.startswith("ask:"))
async def on_ask_button(callback: CallbackQuery) -> None:
    """Нажатие кнопки-подсказки -> сразу отвечаем на типовой вопрос роли."""
    try:
        _, role, lang, idx = callback.data.split(":")
        question = ROLE_QUESTIONS[role][lang][int(idx)][1]
    except Exception:  # noqa: BLE001
        await callback.answer()
        return
    await callback.answer()
    await run_answer(callback.bot, callback.message.chat.id, callback.from_user.id, question)


@dp.message(F.text)
async def on_question(message: Message) -> None:
    question = (message.text or "").strip()
    if not question:
        return
    await run_answer(message.bot, message.chat.id, message.from_user.id, question)


async def main() -> None:
    global retriever
    if not settings.telegram_token:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN в .env")

    logger.info("Загружаю базу знаний...")
    retriever = Retriever()
    if retriever.is_empty:
        logger.warning("База знаний пуста! Сначала запусти: python ingest.py")
    else:
        logger.info("База знаний загружена: %d фрагментов", len(retriever.store))

    bot = Bot(token=settings.telegram_token)
    logger.info("Бот запущен. Ожидаю сообщения...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
