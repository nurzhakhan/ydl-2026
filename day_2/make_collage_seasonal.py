"""Коллаж сезонных блюд (по пикам отзывов из раздела 7). Reuse make_collage.py."""
import os

from PIL import Image, ImageDraw

from make_collage import (CELL, CAPTION_H, TITLE_H, MARGIN, GAP, COLS, ROWS,
                          font, make_image, centered)

# Верхний ряд — холодный сезон, нижний — тёплый. (подпись, "пик", промпт)
DISHES = [
    ("Christmas Cookies", "❄️ пик: декабрь",
     "Professional food photography of decorated Christmas sugar cookies with festive icing"),
    ("Thanksgiving Turkey", "🍂 пик: ноябрь",
     "Professional food photography of a roasted Thanksgiving turkey on a holiday table"),
    ("Soups & Stews", "🍲 пик: январь",
     "Professional food photography of a hearty beef and vegetable stew in a bowl, winter comfort food"),
    ("Summer Salads", "🥗 пик: июнь",
     "Professional food photography of a fresh summer green salad with colorful vegetables in a bowl"),
    ("Grilling / BBQ", "🔥 пик: июль",
     "Professional food photography of grilled meat and vegetables on a barbecue, summer cookout"),
    ("Frozen Desserts", "🍦 пик: июль",
     "Professional food photography of colorful ice cream scoops in a bowl, frozen summer dessert"),
]


def main():
    width = 2 * MARGIN + COLS * CELL + (COLS - 1) * GAP
    height = TITLE_H + 2 * MARGIN + ROWS * (CELL + CAPTION_H) + (ROWS - 1) * GAP
    canvas = Image.new("RGB", (width, height), (250, 248, 245))
    draw = ImageDraw.Draw(canvas)

    centered(draw, width // 2, 40, "Сезонные блюда", font(56, bold=True), (40, 30, 20))
    centered(draw, width // 2, 100, "что готовят в каждый сезон (по пику отзывов за год)",
             font(22), (130, 120, 110))

    for i, (label, meta, prompt) in enumerate(DISHES):
        print(f"[{i+1}/{len(DISHES)}] генерирую: {label}")
        img = make_image(prompt, label)
        col, row = i % COLS, i // COLS
        x = MARGIN + col * (CELL + GAP)
        y = TITLE_H + MARGIN + row * (CELL + CAPTION_H + GAP)
        canvas.paste(img, (x, y))
        centered(draw, x + CELL // 2, y + CELL + 6, label, font(24, bold=True), (40, 30, 20))
        centered(draw, x + CELL // 2, y + CELL + 36, meta, font(21), (190, 90, 40))

    out = os.path.join(os.path.dirname(__file__), "collage_seasonal.png")
    canvas.save(out)
    print("Готово:", out)


if __name__ == "__main__":
    main()
