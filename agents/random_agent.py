from __future__ import annotations

import random

from .base_agent import BaseAgent


class Agent(BaseAgent):
    def __init__(self, player_id: int = 0, seed: int = 0) -> None:
        super().__init__(player_id, seed)
        self.rng = random.Random(seed + player_id * 1009)

    def reset(self, player_id: int, seed: int) -> None:
        super().reset(player_id, seed)
        self.rng.seed(seed + player_id * 1009)

    def decide(self, observation: dict) -> str:
        # Agente propositalmente simples para servir de oponente mínimo.
        return self.rng.choice(["WAIT", "UP", "DOWN", "LEFT", "RIGHT", "BOMB"])
