import os

from dotenv import load_dotenv
from openai import OpenAI

# Читаем секреты из файла .env (он в .gitignore, поэтому ключ не попадёт
# в git). load_dotenv() ищет .env в текущей папке и выше и подгружает его
# значения в os.environ. Если переменная уже задана в окружении
# (например, через export), .env её НЕ перезаписывает.
load_dotenv()

# Эндпоинт alem.ai совместим с OpenAI API, поэтому используем тот же
# клиент, только меняем base_url. И ключ, и URL берём из окружения (.env) —
# единственного источника правды. os.environ[...] упадёт с понятной ошибкой,
# если какой-то из них не задан, поэтому URL не дублируется в коде.
client = OpenAI(
    base_url=os.environ["ALEM_BASE_URL"],
    api_key=os.environ["ALEM_API_KEY"],
)


def ask(prompt):
    """Отправить один вопрос модели и вернуть её ответ как строку."""
    response = client.chat.completions.create(
        model="gemma4",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def main():
    question = input("Спроси что-нибудь у модели: ")
    print(ask(question))


if __name__ == "__main__":
    main()
