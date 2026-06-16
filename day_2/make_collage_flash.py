"""Коллаж блюд-однодневок (вспыхнули и забылись). Переиспользует make_collage.py."""
import os

from PIL import Image, ImageDraw

# Готовые помощники и константы из соседнего скрипта
from make_collage import (CELL, CAPTION_H, TITLE_H, MARGIN, GAP, COLS, ROWS,
                          font, make_image, centered)

# Топ-6 однодневок: (подпись, "отзывов / дней", промпт)
DISHES = [
    ("Tropical Potato Salad", "74 отзыва / 7 дней",
     "Professional food photography of tropical potato salad with pineapple and herbs in a bowl"),
    ("Potato Baskets, Cheese & Bacon", "73 / 39 дней",
     "Professional food photography of shredded potato baskets topped with melted cheese and crispy bacon"),
    ("Animal-Style Skillet Potatoes", "53 / 9 дней",
     "Professional food photography of crispy skillet fried potatoes with caramelized onions, close up"),
    ("Shakshuka (Ragu)", "50 / 10 дней",
     "Professional food photography of shakshuka, eggs poached in spiced tomato sauce in a skillet"),
    ("Roasted Root Veg & Chicken Salad", "47 / 37 дней",
     "Professional food photography of warm roasted root vegetable and grilled chicken salad on a plate"),
    ("Shrimp Nicoise Quiche", "47 / 34 дней",
     "Professional food photography of a slice of shrimp quiche with vegetables on a plate"),
]


def main():
    width = 2 * MARGIN + COLS * CELL + (COLS - 1) * GAP
    height = TITLE_H + 2 * MARGIN + ROWS * (CELL + CAPTION_H) + (ROWS - 1) * GAP
    canvas = Image.new("RGB", (width, height), (250, 248, 245))
    draw = ImageDraw.Draw(canvas)

    centered(draw, width // 2, 40, "Блюда-Однодневки", font(56, bold=True), (40, 30, 20))
    centered(draw, width // 2, 100, "вспыхнули и забылись за пару недель (конкурсные рецепты)",
             font(22), (130, 120, 110))

    for i, (label, meta, prompt) in enumerate(DISHES):
        print(f"[{i+1}/{len(DISHES)}] генерирую: {label}")
        img = make_image(prompt, label)
        col, row = i % COLS, i // COLS
        x = MARGIN + col * (CELL + GAP)
        y = TITLE_H + MARGIN + row * (CELL + CAPTION_H + GAP)
        canvas.paste(img, (x, y))
        centered(draw, x + CELL // 2, y + CELL + 6, label, font(24, bold=True), (40, 30, 20))
        centered(draw, x + CELL // 2, y + CELL + 36, meta, font(22), (190, 90, 40))

    out = os.path.join(os.path.dirname(__file__), "collage_flash.png")
    canvas.save(out)
    print("Готово:", out)


if __name__ == "__main__":
    main()
