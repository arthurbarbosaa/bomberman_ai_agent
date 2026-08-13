from __future__ import annotations

"""Player 3 — k-NN coletor de itens.

Classifica ações por protótipos e acrescenta forte preferência por itens e
caixas. A rota de fuga também tenta terminar perto de power-ups visíveis.
"""

import math
import random

from agents.base_agent import BaseAgent
from players.agent_config import PLAYER_PROFILES
from players.ai_utils import (
    action_features,
    build_context,
    choose_scored_action,
    emergency_escape_action,
    legal_actions,
    safest_action,
)

MODEL_NAME = "k-NN (k=5) — coletor"
PROFILE = PLAYER_PROFILES[3]

GOOD_PROTOTYPES = (
    (1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    (1.0, 1.0, 0.75, 0.8, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    (1.0, 1.0, 0.50, 0.6, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0),
    (1.0, 1.0, 0.75, 0.4, 0.2, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    (1.0, 1.0, 0.50, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0),
    (1.0, 1.0, 0.50, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0),
)
BAD_PROTOTYPES = (
    (-1.0, -1.0, 0.0, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    (-1.0, 1.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    (1.0, -1.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    (1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, -1.0, 0.0, 1.0),
    (1.0, 1.0, 0.25, -1.0, -1.0, -1.0, 0.0, 0.0, 1.0, 1.0, 0.0),
    (1.0, 1.0, 0.25, -1.0, -1.0, -1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
)


class Agent(BaseAgent):
    def __init__(self, player_id: int = 2, seed: int = 0) -> None:
        super().__init__(player_id, seed)
        self.k = 5
        self.rng = random.Random(seed + 3001 * (player_id + 1))
        self.dataset = tuple((row, 1) for row in GOOD_PROTOTYPES) + tuple(
            (row, 0) for row in BAD_PROTOTYPES
        )

    def reset(self, player_id: int, seed: int) -> None:
        super().reset(player_id, seed)
        self.rng.seed(seed + 3001 * (player_id + 1))

    def decide(self, observation: dict) -> str:
        if not observation["self"]["alive"]:
            return "WAIT"
        context = build_context(observation)
        emergency = emergency_escape_action(context, PROFILE.escape_preference, self.rng)
        if emergency is not None:
            return emergency

        scores: dict[str, float] = {}
        for action in legal_actions(context):
            vector = action_features(action, context)[1:]
            probability = self._positive_probability(vector)
            probability += 0.06 * vector[2] + 0.14 * max(0.0, vector[3])
            probability += 0.04 * max(0.0, vector[6])  # caixas destruíveis
            scores[action] = probability
        if not scores:
            return safest_action(context)
        return choose_scored_action(
            scores,
            context,
            self.rng,
            PROFILE.exploration_rate,
            include_bomb_exploration=True,
        )

    def _positive_probability(self, vector: tuple[float, ...]) -> float:
        distances: list[tuple[float, int]] = []
        for prototype, label in self.dataset:
            distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(vector, prototype)))
            distances.append((distance, label))
        neighbours = sorted(distances)[: self.k]
        weighted_positive = 0.0
        total_weight = 0.0
        for distance, label in neighbours:
            weight = 1.0 / (distance + 1e-6)
            weighted_positive += weight * label
            total_weight += weight
        return weighted_positive / total_weight if total_weight else 0.0
