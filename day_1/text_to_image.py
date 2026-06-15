import base64
import os

from dotenv import load_dotenv
from openai import OpenAI

# Секреты и настройки берём из .env (он в .gitignore).
load_dotenv()

# Эндпоинт alem.ai совместим с OpenAI API, поэтому используем тот же клиент.
# У генерации картинок отдельный ключ (ALEM_IMAGE_API_KEY), а base_url тот же,
# что и у чата — SDK сам добавит к нему путь /images/generations.
# И ключ, и URL берём только из .env, чтобы значения не дублировались в коде.
client = OpenAI(
    base_url=os.environ["ALEM_BASE_URL"],
    api_key=os.environ["ALEM_IMAGE_API_KEY"],
)


def generate(prompt, size="512x512"):
    """Сгенерировать картинку по тексту и вернуть её как сырые байты PNG.

    Эндпоинт возвращает картинку в виде base64-строки в поле b64_json,
    поэтому декодируем её обратно в байты.
    """
    response = client.images.generate(
        model="text-to-image",
        prompt=prompt,
        size=size,
    )
    b64 = response.data[0].b64_json
    return base64.b64decode(b64)


def slugify(text):
    """Сделать из промпта безопасное имя файла: только буквы/цифры, через _."""
    keep = [c if c.isalnum() else "_" for c in text.lower()]
    slug = "".join(keep).strip("_")
    # Схлопываем повторяющиеся подчёркивания и ограничиваем длину.
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:40] or "image"


def main():
    prompt = input("Опиши картинку, которую хочешь сгенерировать: ")
    image_bytes = generate(prompt)

    filename = f"{slugify(prompt)}.png"
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "wb") as f:
        f.write(image_bytes)

    print(f"Готово! Картинка сохранена: {path}")


if __name__ == "__main__":
    main()
