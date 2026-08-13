from __future__ import annotations

from dataclasses import dataclass, field

from .enums import Action, ItemType


@dataclass(slots=True)
class Player:
    player_id: int
    name: str
    x: int
    y: int
    alive: bool = True
    max_bombs: int = 1
    active_bombs: int = 0
    bomb_range: int = 2
    move_delay: int = 2
    next_move_tick: int = 0
    shields: int = 0
    score: int = 0
    kills: int = 0
    items_collected: int = 0
    curse_mapping: dict[Action, Action] | None = None
    curse_acquired_tick: int = -1
    curse_immunity_until: int = 0
    last_intended_action: Action = Action.WAIT
    last_effective_action: Action = Action.WAIT

    @property
    def pos(self) -> tuple[int, int]:
        return self.x, self.y

    @pos.setter
    def pos(self, value: tuple[int, int]) -> None:
        self.x, self.y = value

    @property
    def cursed(self) -> bool:
        return self.curse_mapping is not None


@dataclass(slots=True)
class Bomb:
    bomb_id: int
    owner_id: int
    x: int
    y: int
    explode_tick: int
    blast_range: int
    passable_by: set[int] = field(default_factory=set)

    @property
    def pos(self) -> tuple[int, int]:
        return self.x, self.y


@dataclass(slots=True)
class Item:
    item_type: ItemType
    x: int
    y: int

    @property
    def pos(self) -> tuple[int, int]:
        return self.x, self.y


@dataclass(slots=True)
class Flame:
    x: int
    y: int
    expires_tick: int
    owner_id: int
    created_tick: int
    bomb_id: int | None = None
    bomb_position: tuple[int, int] | None = None

    @property
    def pos(self) -> tuple[int, int]:
        return self.x, self.y


@dataclass(slots=True)
class GameResult:
    winner_ids: list[int]
    reason: str
    ticks: int
    standings: list[dict]
