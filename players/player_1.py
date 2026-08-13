from __future__ import annotations

"""Player 1 — perceptron linear defensivo.

Prioriza sobrevivência e mobilidade. Usa pouca exploração e, ao fugir, escolhe
células mais distantes das zonas ameaçadas.
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

MODEL_NAME = "Perceptron linear — defensivo"
PROFILE = PLAYER_PROFILES[1]


class Agent(BaseAgent):
    def __init__(self, player_id: int = 0, seed: int = 0) -> None:
        super().__init__(player_id, seed)
        self.rng = random.Random(seed + 1009 * (player_id + 1))
        self.weights = (
            0.05, 8.0, 4.0, 2.8, 1.6, -0.2, 0.4,
            1.5, 1.6, 6.0, -0.8, -1.1,
        )

    def reset(self, player_id: int, seed: int) -> None:
        super().reset(player_id, seed)
        self.rng.seed(seed + 1009 * (player_id + 1))

    def decide(self, observation: dict) -> str:
        if not observation["self"]["alive"]:
            return "WAIT"
        context = build_context(observation)
        emergency = emergency_escape_action(context, PROFILE.escape_preference, self.rng)
        if emergency is not None:
            return emergency

        scores = {
            action: sum(
                weight * value
                for weight, value in zip(self.weights, action_features(action, context))
            )
            for action in legal_actions(context)
        }
        if not scores:
            return safest_action(context)
        return choose_scored_action(
            scores,
            context,
            self.rng,
            PROFILE.exploration_rate,
            include_bomb_exploration=False,
        )
