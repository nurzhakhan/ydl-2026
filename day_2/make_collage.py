"""Собрать коллаж фото блюд-долгожителей через alem.ai text-to-image."""
import base64
import io
import os

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

# Ключи alem.ai лежат в корневом .env (на уровень выше day_2)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client = OpenAI(
    base_url=os.environ["ALEM_BASE_URL"],
    api_key=os.environ["ALEM_IMAGE_API_KEY"],
)

# Топ-6 долгожителей: (подпись, размах лет, промпт для фото)
DISHES = [
    ("Chocolate Chip Cookies", "18.5 лет",
     "Professional food photography of fresh chocolate chip cookies on a plate, warm lighting, top view"),
    ("Buffalo Wings", "18.0 лет",
     "Professional food photography of buffalo chicken wings with hot sauce, restaurant style, close up"),
    ("French Onion Soup", "18.0 лет",
     "Professional food photography of French onion soup with melted cheese on top, in a bowl"),
    ("Corned Beef", "18.0 лет",
     "Professional food photography of sliced corned beef with cabbage and potatoes on a plate"),
    ("Chicken, Gravy & Stuffing", "17.9 лет",
     "Professional food photography of roast chicken with gravy and stuffing, home cooked dinner plate"),
    ("Chicken Tortilla Soup", "17.9 лет",
     "Professional food photography of chicken tortilla soup with crispy tortilla strips and avocado in a bowl"),
]

CELL = 512          # размер фото
CAPTION_H = 60      # полоса подписи под фото
TITLE_H = 130       # шапка с заголовком
MARGIN = 30
GAP = 20
COLS, ROWS = 3, 2


def font(size, bold=False):
    """Шрифт с поддержкой кириллицы (Arial есть в macOS)."""
    for path in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_image(prompt, label):
    """Сгенерировать фото; при ошибке вернуть серую заглушку с подписью."""
    try:
        resp = client.images.generate(model="text-to-image", prompt=prompt, size=f"{CELL}x{CELL}")
        img = Image.open(io.BytesIO(base64.b64decode(resp.data[0].b64_json))).convert("RGB")
        return img.resize((CELL, CELL))
    except Exception as e:
        print(f"  ! не вышло для '{label}': {str(e)[:80]}")
        ph = Image.new("RGB", (CELL, CELL), (200, 200, 200))
        ImageDraw.Draw(ph).text((CELL // 2, CELL // 2), label, fill=(90, 90, 90),
                                font=font(28, bold=True), anchor="mm")
        return ph


def centered(draw, cx, y, text, fnt, fill):
    draw.text((cx, y), text, fill=fill, font=fnt, anchor="ma")


def main():
    width = 2 * MARGIN + COLS * CELL + (COLS - 1) * GAP
    height = TITLE_H + 2 * MARGIN + ROWS * (CELL + CAPTION_H) + (ROWS - 1) * GAP
    canvas = Image.new("RGB", (width, height), (250, 248, 245))
    draw = ImageDraw.Draw(canvas)

    # Заголовок
    centered(draw, width // 2, 40, "Блюды Долгожители", font(56, bold=True), (40, 30, 20))
    centered(draw, width // 2, 100, "рецепты, которые готовят ~18 лет подряд",
             font(24), (130, 120, 110))

    for i, (label, years, prompt) in enumerate(DISHES):
        print(f"[{i+1}/{len(DISHES)}] генерирую: {label}")
        img = make_image(prompt, label)
        col, row = i % COLS, i // COLS
        x = MARGIN + col * (CELL + GAP)
        y = TITLE_H + MARGIN + row * (CELL + CAPTION_H + GAP)
        canvas.paste(img, (x, y))
        centered(draw, x + CELL // 2, y + CELL + 6, label, font(26, bold=True), (40, 30, 20))
        centered(draw, x + CELL // 2, y + CELL + 36, years, font(22), (190, 90, 40))

    out = os.path.join(os.path.dirname(__file__), "collage_longlived.png")
    canvas.save(out)
    print("Готово:", out)


if __name__ == "__main__":
    main()
