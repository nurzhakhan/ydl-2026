"""Коллаж «Любимое, но вредное» — высокий рейтинг, рекордный сахар. Reuse make_collage.py."""
import os

from PIL import Image, ImageDraw

from make_collage import (CELL, CAPTION_H, TITLE_H, MARGIN, GAP, COLS, ROWS,
                          font, make_image, centered)

# Топ-6 по сахару среди любимых (★>=4.5, >=50 оценок): (подпись, "★рейтинг · сахар", промпт)
DISHES = [
    ("Maple Brine", "★ 4.76 · сахар 2508%",
     "Professional food photography of a maple-glazed roasted turkey, golden glossy skin"),
    ("Pineapple Upside-Down Cake", "★ 4.77 · сахар 2154%",
     "Professional food photography of pineapple upside-down cake with caramelized pineapple rings and cherries"),
    ("Buttercream Frosting", "★ 4.92 · сахар 1880%",
     "Professional food photography of a cupcake topped with thick swirled buttercream frosting, close up"),
    ("Apple Pie Jam", "★ 4.69 · сахар 1419%",
     "Professional food photography of apple pie jam in a glass jar with fresh apples and cinnamon sticks"),
    ("Cream Cheese Coffee Cake", "★ 4.82 · сахар 1325%",
     "Professional food photography of cream cheese almond coffee cake slice with crumb topping"),
    ("Cinnamon Swirl Bread", "★ 4.79 · сахар 1115%",
     "Professional food photography of cinnamon swirl quick bread loaf, sliced to show the swirl"),
]


def main():
    width = 2 * MARGIN + COLS * CELL + (COLS - 1) * GAP
    height = TITLE_H + 2 * MARGIN + ROWS * (CELL + CAPTION_H) + (ROWS - 1) * GAP
    canvas = Image.new("RGB", (width, height), (250, 248, 245))
    draw = ImageDraw.Draw(canvas)

    centered(draw, width // 2, 40, "Любимое, но вредное", font(56, bold=True), (40, 30, 20))
    centered(draw, width // 2, 100, "обожают (★ 4.5+), но рекордсмены по сахару (% дневной нормы)",
             font(22), (130, 120, 110))

    for i, (label, meta, prompt) in enumerate(DISHES):
        print(f"[{i+1}/{len(DISHES)}] генерирую: {label}")
        img = make_image(prompt, label)
        col, row = i % COLS, i // COLS
        x = MARGIN + col * (CELL + GAP)
        y = TITLE_H + MARGIN + row * (CELL + CAPTION_H + GAP)
        canvas.paste(img, (x, y))
        centered(draw, x + CELL // 2, y + CELL + 6, label, font(24, bold=True), (40, 30, 20))
        centered(draw, x + CELL // 2, y + CELL + 36, meta, font(20), (190, 90, 40))

    out = os.path.join(os.path.dirname(__file__), "collage_loved.png")
    canvas.save(out)
    print("Готово:", out)


if __name__ == "__main__":
    main()
