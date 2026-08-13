from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GameConfig:
    width: int = 15
    height: int = 13
    crate_density: float = 0.42
    item_probability: float = 0.28

    ticks_per_second: int = 8
    bomb_fuse_ticks: int = 24
    flame_duration_ticks: int = 4
    active_flames_block_movement: bool = True
    initial_bomb_range: int = 2
    initial_max_bombs: int = 1
    initial_move_delay: int = 2
    minimum_move_delay: int = 1

    shrink_start_tick: int = 8 * 75
    shrink_interval_ticks: int = 8 * 7
    max_ticks: int = 8 * 150

    curse_source_immunity_ticks: int = 12
    reveal_curse_mapping: bool = False
    agent_timeout_ms: int = 80

    def validate(self) -> None:
        if self.width < 11 or self.height < 11:
            raise ValueError("A arena deve ter pelo menos 11x11 células.")
        if self.width % 2 == 0 or self.height % 2 == 0:
            raise ValueError("Use largura e altura ímpares.")
        if not 0.0 <= self.crate_density <= 0.8:
            raise ValueError("crate_density deve ficar entre 0 e 0.8.")
        if not 0.0 <= self.item_probability <= 1.0:
            raise ValueError("item_probability deve ficar entre 0 e 1.")
