from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "assets" / "sprites"
ROOT.mkdir(parents=True, exist_ok=True)
SIZE = 32


def save(img: Image.Image, name: str) -> None:
    img.save(ROOT / name)


def canvas(bg=(0, 0, 0, 0)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (SIZE, SIZE), bg)
    return image, ImageDraw.Draw(image)


def tile_floor() -> Image.Image:
    img, d = canvas((180, 199, 146, 255))
    d.rectangle((0, 0, 31, 31), fill=(190, 207, 156, 255))
    for y in range(0, 32, 8):
        d.line((0, y, 31, y), fill=(167, 188, 132, 255), width=1)
    for x in range(0, 32, 8):
        offset = 4 if (x // 8) % 2 else 0
        d.line((x, offset, x, 31), fill=(174, 194, 140, 255), width=1)
    return img


def tile_wall() -> Image.Image:
    img, d = canvas((72, 93, 116, 255))
    d.rectangle((1, 1, 30, 30), fill=(87, 112, 139, 255), outline=(35, 51, 68, 255), width=2)
    d.rectangle((4, 4, 27, 12), fill=(116, 143, 169, 255))
    d.rectangle((4, 15, 14, 27), fill=(102, 130, 157, 255))
    d.rectangle((17, 15, 27, 27), fill=(102, 130, 157, 255))
    d.line((3, 14, 28, 14), fill=(40, 58, 76, 255), width=2)
    d.line((15, 14, 15, 29), fill=(40, 58, 76, 255), width=2)
    return img


def tile_crate() -> Image.Image:
    img, d = canvas()
    d.rectangle((2, 2, 29, 29), fill=(151, 92, 43, 255), outline=(76, 42, 22, 255), width=2)
    d.rectangle((6, 6, 25, 25), outline=(218, 148, 72, 255), width=2)
    d.line((6, 6, 25, 25), fill=(91, 49, 24, 255), width=3)
    d.line((25, 6, 6, 25), fill=(91, 49, 24, 255), width=3)
    d.rectangle((12, 12, 19, 19), fill=(180, 113, 51, 255), outline=(91, 49, 24, 255))
    return img


def tile_shrink() -> Image.Image:
    img, d = canvas((31, 31, 36, 255))
    d.rectangle((1, 1, 30, 30), fill=(42, 42, 48, 255), outline=(8, 8, 10, 255), width=2)
    for i in range(-24, 40, 10):
        d.line((i, 31, i + 31, 0), fill=(181, 49, 49, 255), width=4)
    d.rectangle((2, 2, 29, 29), outline=(245, 185, 45, 255), width=2)
    return img


def bomb(frame: int) -> Image.Image:
    img, d = canvas()
    radius = 10 + (1 if frame == 1 else 0)
    cx, cy = 16, 18
    d.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=(28, 30, 34, 255), outline=(6, 6, 8, 255), width=2)
    d.ellipse((10, 10, 14, 14), fill=(115, 124, 134, 255))
    d.arc((15, 1, 28, 15), start=180, end=300, fill=(64, 42, 24, 255), width=3)
    fuse = [(26, 6), (28, 4), (30, 7), (28, 9)]
    spark = (255, 235, 75, 255) if frame != 2 else (255, 90, 40, 255)
    d.polygon(fuse, fill=spark)
    if frame == 2:
        d.line((24, 4, 30, 10), fill=(255, 220, 70, 255), width=2)
        d.line((30, 4, 24, 10), fill=(255, 220, 70, 255), width=2)
    return img


def flame(frame: int) -> Image.Image:
    img, d = canvas()
    outer = [(16, 2), (21, 10), (25, 7), (26, 17), (30, 20), (23, 29), (9, 29), (2, 20), (7, 16), (6, 8), (12, 11)]
    if frame:
        outer = [(x + (1 if y < 14 and x < 16 else -1 if y < 14 else 0), y) for x, y in outer]
    d.polygon(outer, fill=(244, 74, 36, 255))
    d.polygon([(16, 7), (20, 14), (23, 13), (23, 21), (19, 27), (12, 27), (8, 21), (12, 17), (11, 12)], fill=(255, 176, 43, 255))
    d.polygon([(16, 13), (19, 19), (17, 25), (13, 24), (12, 20)], fill=(255, 244, 129, 255))
    return img


PLAYER_ACCENTS = [
    (45, 117, 236, 255),
    (227, 62, 67, 255),
    (57, 167, 103, 255),
    (161, 83, 211, 255),
]


def player(player_index: int, direction: str, frame: int) -> Image.Image:
    img, d = canvas()
    accent = PLAYER_ACCENTS[player_index]
    dark = tuple(max(0, c - 55) for c in accent[:3]) + (255,)
    skin = (242, 188, 145, 255)
    white = (242, 245, 247, 255)
    black = (22, 25, 30, 255)

    # sombra
    d.ellipse((7, 26, 25, 30), fill=(0, 0, 0, 75))
    # pernas alternadas
    if frame == 0:
        d.rectangle((9, 22, 14, 28), fill=white, outline=black)
        d.rectangle((18, 22, 23, 28), fill=white, outline=black)
    else:
        d.rectangle((7, 22, 13, 28), fill=white, outline=black)
        d.rectangle((19, 21, 25, 27), fill=white, outline=black)
    # corpo e braços
    d.rounded_rectangle((8, 11, 24, 24), radius=4, fill=accent, outline=dark, width=2)
    d.rectangle((4, 13, 9, 20), fill=skin, outline=black)
    d.rectangle((23, 13, 28, 20), fill=skin, outline=black)
    # cabeça/capacete
    d.ellipse((7, 2, 25, 18), fill=white, outline=black, width=2)
    d.rectangle((8, 4, 24, 10), fill=white)
    d.rectangle((11, 1, 21, 5), fill=accent, outline=dark)
    d.rectangle((14, 0, 18, 3), fill=accent)
    # viseira/faixa
    d.rectangle((9, 8, 23, 12), fill=accent, outline=dark)

    if direction == "up":
        d.rectangle((12, 9, 20, 11), fill=dark)
    elif direction == "left":
        d.rectangle((9, 9, 13, 12), fill=skin)
        d.rectangle((10, 9, 11, 10), fill=black)
    elif direction == "right":
        d.rectangle((19, 9, 23, 12), fill=skin)
        d.rectangle((21, 9, 22, 10), fill=black)
    else:
        d.rectangle((11, 8, 15, 12), fill=skin)
        d.rectangle((18, 8, 22, 12), fill=skin)
        d.rectangle((13, 9, 14, 10), fill=black)
        d.rectangle((19, 9, 20, 10), fill=black)

    # detalhe identificador
    d.rectangle((14, 16, 18, 20), fill=(255, 223, 80, 255), outline=dark)
    return img


def item_icon(kind: str) -> Image.Image:
    img, d = canvas()
    d.ellipse((3, 3, 29, 29), fill=(255, 221, 64, 255), outline=(100, 72, 12, 255), width=2)
    if kind == "bomb_up":
        d.ellipse((8, 11, 20, 23), fill=(30, 32, 36, 255), outline=(0, 0, 0, 255))
        d.arc((16, 5, 26, 15), 180, 300, fill=(70, 42, 20, 255), width=2)
        d.line((23, 7, 28, 7), fill=(218, 55, 40, 255), width=2)
        d.line((25, 5, 25, 10), fill=(218, 55, 40, 255), width=2)
    elif kind == "range_up":
        d.line((7, 16, 25, 16), fill=(215, 55, 38, 255), width=4)
        d.polygon([(7, 16), (12, 11), (12, 21)], fill=(215, 55, 38, 255))
        d.polygon([(25, 16), (20, 11), (20, 21)], fill=(215, 55, 38, 255))
    elif kind == "speed_up":
        d.polygon([(8, 20), (15, 7), (15, 14), (24, 14), (16, 26), (16, 20)], fill=(48, 114, 220, 255), outline=(24, 65, 135, 255))
    elif kind == "shield":
        d.polygon([(16, 6), (24, 9), (23, 18), (16, 26), (9, 18), (8, 9)], fill=(90, 191, 235, 255), outline=(28, 88, 120, 255))
        d.polygon([(16, 9), (20, 11), (19, 17), (16, 21), (13, 17), (12, 11)], fill=(210, 244, 255, 255))
    elif kind == "curse":
        d.ellipse((9, 8, 14, 13), fill=(122, 46, 155, 255))
        d.ellipse((18, 8, 23, 13), fill=(122, 46, 155, 255))
        d.arc((10, 13, 23, 24), 190, 350, fill=(122, 46, 155, 255), width=3)
        d.line((16, 3, 16, 7), fill=(122, 46, 155, 255), width=2)
    return img


def main() -> None:
    save(tile_floor(), "floor.png")
    save(tile_wall(), "wall.png")
    save(tile_crate(), "crate.png")
    save(tile_shrink(), "shrink_wall.png")
    for frame in range(3):
        save(bomb(frame), f"bomb_{frame}.png")
    for frame in range(2):
        save(flame(frame), f"flame_{frame}.png")
    for index in range(4):
        for direction in ("down", "up", "left", "right"):
            for frame in range(2):
                save(player(index, direction, frame), f"player_{index + 1}_{direction}_{frame}.png")
    for kind in ("bomb_up", "range_up", "speed_up", "shield", "curse"):
        save(item_icon(kind), f"item_{kind}.png")
    print(f"Sprites gerados em: {ROOT}")


if __name__ == "__main__":
    main()
