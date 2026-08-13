from __future__ import annotations

from enum import Enum, IntEnum


class Action(str, Enum):
    WAIT = "WAIT"
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    BOMB = "BOMB"


MOVE_DELTAS: dict[Action, tuple[int, int]] = {
    Action.UP: (0, -1),
    Action.DOWN: (0, 1),
    Action.LEFT: (-1, 0),
    Action.RIGHT: (1, 0),
}


class Tile(IntEnum):
    FLOOR = 0
    WALL = 1
    CRATE = 2
    SHRINK_WALL = 3


class ItemType(str, Enum):
    BOMB_UP = "BOMB_UP"
    RANGE_UP = "RANGE_UP"
    SPEED_UP = "SPEED_UP"
    SHIELD = "SHIELD"
    CURSE = "CURSE"
