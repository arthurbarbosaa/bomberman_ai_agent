from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Contrato mínimo para os agentes dos alunos."""

    def __init__(self, player_id: int = 0, seed: int = 0) -> None:
        self.player_id = player_id
        self.seed = seed

    def reset(self, player_id: int, seed: int) -> None:
        self.player_id = player_id
        self.seed = seed

    @abstractmethod
    def decide(self, observation: dict) -> str:
        """Retorne WAIT, UP, DOWN, LEFT, RIGHT ou BOMB."""
        raise NotImplementedError
