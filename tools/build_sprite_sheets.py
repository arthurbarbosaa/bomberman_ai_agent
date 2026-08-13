from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
SHEETS = ROOT / "assets" / "sheets"
CELL = 32


def _sheet(frames: list[Image.Image], path: Path) -> None:
    canvas = Image.new("RGBA", (CELL * len(frames), CELL), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        canvas.alpha_composite(frame.convert("RGBA"), (index * CELL, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def build_players() -> None:
    # Convenção compatível com o projeto de referência:
    # 0..2 cima, 3..5 direita, 6..8 baixo, 9..11 esquerda.
    for player in range(1, 5):
        frames: list[Image.Image] = []
        for direction in ("up", "right", "down", "left"):
            first = Image.open(SPRITES / f"player_{player}_{direction}_0.png").convert("RGBA")
            second = Image.open(SPRITES / f"player_{player}_{direction}_1.png").convert("RGBA")
            frames.extend((first, second, first.copy()))
        _sheet(frames, SHEETS / f"player_{player}.png")


def build_bomb() -> None:
    frames = [Image.open(SPRITES / f"bomb_{index}.png").convert("RGBA") for index in range(3)]
    _sheet(frames, SHEETS / "bomb.png")


def _flame_frame(part: str, pulse: int) -> Image.Image:
    image = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    outer = (255, 105 + 25 * pulse, 20, 255)
    inner = (255, 225, 75 + 25 * pulse, 255)
    cx, cy = CELL // 2, CELL // 2
    thick = 7 + pulse
    core = 5

    def rect(box, fill):
        draw.rectangle(box, fill=fill)

    # Segmentos externos.
    if part in {"center", "horizontal", "end_left", "end_right"}:
        rect((2, cy - thick, CELL - 3, cy + thick), outer)
        rect((3, cy - core, CELL - 4, cy + core), inner)
    if part in {"center", "vertical", "end_up", "end_down"}:
        rect((cx - thick, 2, cx + thick, CELL - 3), outer)
        rect((cx - core, 3, cx + core, CELL - 4), inner)

    # Afunila pontas para indicar a direção terminal.
    if part == "end_left":
        draw.polygon([(1, cy), (10, cy - thick), (10, cy + thick)], fill=outer)
        draw.polygon([(2, cy), (11, cy - core), (11, cy + core)], fill=inner)
    elif part == "end_right":
        draw.polygon([(CELL - 2, cy), (CELL - 11, cy - thick), (CELL - 11, cy + thick)], fill=outer)
        draw.polygon([(CELL - 3, cy), (CELL - 12, cy - core), (CELL - 12, cy + core)], fill=inner)
    elif part == "end_up":
        draw.polygon([(cx, 1), (cx - thick, 10), (cx + thick, 10)], fill=outer)
        draw.polygon([(cx, 2), (cx - core, 11), (cx + core, 11)], fill=inner)
    elif part == "end_down":
        draw.polygon([(cx, CELL - 2), (cx - thick, CELL - 11), (cx + thick, CELL - 11)], fill=outer)
        draw.polygon([(cx, CELL - 3), (cx - core, CELL - 12), (cx + core, CELL - 12)], fill=inner)

    # Núcleo comum para esconder emendas entre segmentos.
    draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=outer)
    draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=inner)
    return image


def build_flames() -> None:
    parts = ("center", "horizontal", "vertical", "end_up", "end_right", "end_down", "end_left")
    frames = [_flame_frame(part, pulse) for part in parts for pulse in (0, 1)]
    _sheet(frames, SHEETS / "flames.png")


def build_preview() -> None:
    rows = []
    for player in range(1, 5):
        rows.append(Image.open(SHEETS / f"player_{player}.png").convert("RGBA"))
    rows.append(Image.open(SHEETS / "bomb.png").convert("RGBA"))
    rows.append(Image.open(SHEETS / "flames.png").convert("RGBA"))
    width = max(row.width for row in rows)
    height = sum(row.height for row in rows)
    preview = Image.new("RGBA", (width, height), (32, 36, 44, 255))
    y = 0
    for row in rows:
        preview.alpha_composite(row, (0, y))
        y += row.height
    preview.save(ROOT / "assets" / "sprite_sheets_preview.png")


def main() -> None:
    build_players()
    build_bomb()
    build_flames()
    build_preview()
    print(f"Sprite sheets gerados em: {SHEETS}")


if __name__ == "__main__":
    main()
