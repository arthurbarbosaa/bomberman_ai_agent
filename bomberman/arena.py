from __future__ import annotations

import random
from dataclasses import dataclass

from .enums import ItemType, Tile


@dataclass(slots=True)
class ArenaData:
    grid: list[list[Tile]]
    spawns: list[tuple[int, int]]
    hidden_items: dict[tuple[int, int], ItemType]


def _spawn_positions(width: int, height: int) -> list[tuple[int, int]]:
    return [(1, 1), (width - 2, height - 2), (width - 2, 1), (1, height - 2)]


def _safe_cells_for_spawn(
    spawn: tuple[int, int], width: int, height: int
) -> set[tuple[int, int]]:
    x, y = spawn
    dx = 1 if x < width // 2 else -1
    dy = 1 if y < height // 2 else -1

    # Dois corredores em L. Assim, após colocar a primeira bomba, o jogador
    # tem como sair da linha de explosão antes do fim do pavio.
    offsets = {
        (0, 0),
        (dx, 0),
        (2 * dx, 0),
        (2 * dx, dy),
        (0, dy),
        (0, 2 * dy),
        (dx, 2 * dy),
    }
    return {(x + ox, y + oy) for ox, oy in offsets}


def generate_arena(
    width: int,
    height: int,
    player_count: int,
    crate_density: float,
    item_probability: float,
    seed: int,
) -> ArenaData:
    if not 2 <= player_count <= 4:
        raise ValueError("Esta versão aceita de 2 a 4 jogadores.")

    rng = random.Random(seed)
    grid = [[Tile.FLOOR for _ in range(width)] for _ in range(height)]

    for y in range(height):
        for x in range(width):
            border = x == 0 or y == 0 or x == width - 1 or y == height - 1
            pillar = x % 2 == 0 and y % 2 == 0
            if border or pillar:
                grid[y][x] = Tile.WALL

    all_spawns = _spawn_positions(width, height)
    spawns = all_spawns[:player_count]
    protected: set[tuple[int, int]] = set()
    for spawn in spawns:
        protected.update(_safe_cells_for_spawn(spawn, width, height))

    hidden_items: dict[tuple[int, int], ItemType] = {}
    weighted_items = [
        ItemType.BOMB_UP,
        ItemType.BOMB_UP,
        ItemType.RANGE_UP,
        ItemType.RANGE_UP,
        ItemType.SPEED_UP,
        ItemType.SHIELD,
        ItemType.CURSE,
    ]

    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if grid[y][x] != Tile.FLOOR or (x, y) in protected:
                continue
            if rng.random() < crate_density:
                grid[y][x] = Tile.CRATE
                if rng.random() < item_probability:
                    hidden_items[(x, y)] = rng.choice(weighted_items)

    # Garante itens suficientes e pelo menos uma unidade de cada mecânica,
    # incluindo obrigatoriamente a maldição.
    crate_positions = [
        (x, y)
        for y in range(height)
        for x in range(width)
        if grid[y][x] == Tile.CRATE
    ]
    rng.shuffle(crate_positions)
    minimum_items = min(max(4, player_count * 2), len(crate_positions))
    for pos in crate_positions:
        if len(hidden_items) >= minimum_items:
            break
        hidden_items.setdefault(pos, rng.choice(weighted_items))

    required_items = list(ItemType)
    for pos, item_type in zip(crate_positions, required_items):
        hidden_items[pos] = item_type

    return ArenaData(grid=grid, spawns=spawns, hidden_items=hidden_items)
