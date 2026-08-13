from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bomberman.config import GameConfig
from bomberman.engine import GameEngine
from bomberman.enums import ItemType, Tile
from bomberman.state import Item

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
SHEETS = ROOT / "assets" / "sheets"
CELL = 32


def frame(sheet_name: str, index: int) -> Image.Image:
    sheet = Image.open(SHEETS / sheet_name).convert("RGBA")
    return sheet.crop((index * CELL, 0, (index + 1) * CELL, CELL))


def main() -> None:
    engine = GameEngine(
        ["player_1", "player_2", "player_3", "player_4"],
        seed=42,
        config=GameConfig(width=15, height=13),
    )
    width = engine.width * CELL
    panel = 92
    canvas = Image.new("RGBA", (width, engine.height * CELL + panel), (22, 25, 31, 255))

    tile_names = {
        Tile.FLOOR: "floor.png",
        Tile.WALL: "wall.png",
        Tile.CRATE: "crate.png",
        Tile.SHRINK_WALL: "shrink_wall.png",
    }
    tiles = {key: Image.open(SPRITES / name).convert("RGBA") for key, name in tile_names.items()}
    for y, row in enumerate(engine.grid):
        for x, tile in enumerate(row):
            canvas.alpha_composite(tiles[tile], (x * CELL, y * CELL))

    # Pequena cena demonstrativa sem alterar o motor distribuído.
    demo_items = [
        Item(ItemType.BOMB_UP, 3, 1),
        Item(ItemType.RANGE_UP, 11, 1),
        Item(ItemType.SHIELD, 3, 11),
        Item(ItemType.CURSE, 11, 11),
    ]
    item_names = {
        ItemType.BOMB_UP: "item_bomb_up.png",
        ItemType.RANGE_UP: "item_range_up.png",
        ItemType.SPEED_UP: "item_speed_up.png",
        ItemType.SHIELD: "item_shield.png",
        ItemType.CURSE: "item_curse.png",
    }
    for item in demo_items:
        if engine.grid[item.y][item.x] == Tile.FLOOR:
            icon = Image.open(SPRITES / item_names[item.item_type]).convert("RGBA")
            canvas.alpha_composite(icon, (item.x * CELL, item.y * CELL))

    # Bomba e explosão segmentada no centro, apenas para prévia visual.
    center = (7, 5)
    if engine.grid[center[1]][center[0]] == Tile.FLOOR:
        canvas.alpha_composite(frame("bomb.png", 2), (center[0] * CELL, center[1] * CELL))
    flame_frames = {
        (7, 6): 4,  # vertical
        (7, 7): 10,  # ponta inferior
        (6, 5): 2,  # horizontal
        (5, 5): 12,  # ponta esquerda
        (8, 5): 2,
        (9, 5): 8,  # ponta direita
    }
    for (x, y), index in flame_frames.items():
        if engine.grid[y][x] == Tile.FLOOR:
            canvas.alpha_composite(frame("flames.png", index), (x * CELL, y * CELL))

    direction_indices = [7, 10, 4, 1]
    for pid, player in engine.players.items():
        canvas.alpha_composite(
            frame(f"player_{pid + 1}.png", direction_indices[pid]),
            (player.x * CELL, player.y * CELL),
        )

    draw = ImageDraw.Draw(canvas)
    board_height = engine.height * CELL
    draw.rectangle((0, board_height, width, board_height + panel), fill=(18, 20, 25, 255))
    font = ImageFont.load_default()
    draw.text((10, board_height + 10), "BOMBERMAN AI ARENA — V3", font=font, fill=(245, 245, 245, 255))
    draw.text(
        (10, board_height + 32),
        "4 agentes independentes | spritesheets | arena aleatoria | itens | curse",
        font=font,
        fill=(205, 215, 230, 255),
    )
    draw.text(
        (10, board_height + 52),
        "Logica discreta: movimento -> explosao -> dano -> animacao auditavel",
        font=font,
        fill=(255, 205, 125, 255),
    )

    output = ROOT / "assets" / "v3_game_preview.png"
    canvas.save(output)
    print(output)


if __name__ == "__main__":
    main()
