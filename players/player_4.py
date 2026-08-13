from __future__ import annotations

"""Player 4 — rede neural MLP territorial.

A MLP valoriza o centro, mobilidade e controle de corredores. Sua fuga busca
células seguras que preservem posição territorial.
"""

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

MODEL_NAME = "Rede neural MLP 12-6-1 — territorial"
PROFILE = PLAYER_PROFILES[4]


class Agent(BaseAgent):
    def __init__(self, player_id: int = 3, seed: int = 0) -> None:
        super().__init__(player_id, seed)
        self.rng = random.Random(seed + 4001 * (player_id + 1))
        self.hidden_weights = (
            (0.0, 3.4, 1.8, 0.8, 0.0, 0.0, 0.3, 0.0, 0.0, 1.7, 0.0, 0.0),
            (0.0, 1.0, 0.8, 0.6, 0.5, 0.0, 1.4, 0.0, 0.0, 0.4, 0.0, 0.0),
            (0.0, 0.8, 0.4, 0.2, 0.0, 1.0, 0.8, 1.2, 2.4, 2.0, 0.0, 0.5),
            (0.0, 0.8, 0.8, 0.5, 0.0, 0.0, 3.8, 0.0, 0.0, 0.2, 0.0, 0.0),
            (0.0, 1.0, 0.8, 3.0, 0.2, 0.2, 0.8, 0.0, 0.0, 0.4, 0.0, 0.0),
            (0.0, 1.6, 1.0, 0.4, 0.0, 0.0, 1.0, 0.0, 0.0, 2.5, -2.0, -0.8),
        )
        self.hidden_bias = (-1.2, -1.0, -1.1, -0.8, -1.0, -0.6)
        self.output_weights = (1.5, 1.1, 1.0, 1.4, 1.0, 1.2)
        self.output_bias = -0.2

    def reset(self, player_id: int, seed: int) -> None:
        super().reset(player_id, seed)
        self.rng.seed(seed + 4001 * (player_id + 1))

    def decide(self, observation: dict) -> str:
        if not observation["self"]["alive"]:
            return "WAIT"
        context = build_context(observation)
        emergency = emergency_escape_action(context, PROFILE.escape_preference, self.rng)
        if emergency is not None:
            return emergency

        scores = {
            action: self._forward(action_features(action, context))
            for action in legal_actions(context)
        }
        if not scores:
            return safest_action(context)
        return choose_scored_action(
            scores,
            context,
            self.rng,
            PROFILE.exploration_rate,
            include_bomb_exploration=True,
        )

    def _forward(self, features: tuple[float, ...]) -> float:
        hidden = []
        for weights, bias in zip(self.hidden_weights, self.hidden_bias):
            activation = bias + sum(w * x for w, x in zip(weights, features))
            hidden.append(max(0.0, activation))
        return self.output_bias + sum(w * h for w, h in zip(self.output_weights, hidden))
