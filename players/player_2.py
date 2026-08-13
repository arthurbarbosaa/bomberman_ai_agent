from __future__ import annotations

"""Player 2 — árvore de decisão agressiva.

Procura adversários, coloca bombas com mais frequência e mantém rotas de fuga
próximas do combate. Há exploração controlada para evitar decisões idênticas.
"""

import random

from agents.base_agent import BaseAgent
from players.agent_config import PLAYER_PROFILES
from players.ai_utils import (
    action_features,
    adjacent_crate,
    build_context,
    choose_scored_action,
    distance_progress,
    emergency_escape_action,
    escape_exists_after_bomb,
    legal_actions,
    safest_action,
    target_for,
)

MODEL_NAME = "Árvore de decisão — agressiva"
PROFILE = PLAYER_PROFILES[2]


class Agent(BaseAgent):
    def __init__(self, player_id: int = 1, seed: int = 0) -> None:
        super().__init__(player_id, seed)
        self.rng = random.Random(seed + 2003 * (player_id + 1))
        self.last_action = "WAIT"

    def reset(self, player_id: int, seed: int) -> None:
        super().reset(player_id, seed)
        self.rng.seed(seed + 2003 * (player_id + 1))
        self.last_action = "WAIT"

    def decide(self, observation: dict) -> str:
        if not observation["self"]["alive"]:
            return "WAIT"
        context = build_context(observation)
        emergency = emergency_escape_action(context, PROFILE.escape_preference, self.rng)
        if emergency is not None:
            return emergency

        actions = legal_actions(context)
        moves = [a for a in actions if a not in ("WAIT", "BOMB")]
        enemy_close = any(
            abs(context.current[0] - x) + abs(context.current[1] - y)
            <= context.bomb_range
            for x, y in context.opponents
        )

        # Ramo ofensivo: normalmente ataca, mas nem sempre repete a mesma jogada.
        if (
            "BOMB" in actions
            and escape_exists_after_bomb(context)
            and (enemy_close or adjacent_crate(context.current, context.board))
            and self.rng.random() < 0.82
        ):
            self.last_action = "BOMB"
            return "BOMB"

        if context.items and self.rng.random() < 0.30:
            objective = "item"
        elif context.shrink.get("active"):
            objective = "center"
        else:
            objective = "enemy"

        scores = self._move_scores(context, moves, objective)
        if "WAIT" in actions:
            scores["WAIT"] = -0.5
        action = choose_scored_action(
            scores,
            context,
            self.rng,
            PROFILE.exploration_rate,
            include_bomb_exploration=True,
        )
        self.last_action = action
        return action

    @staticmethod
    def _move_scores(context, moves: list[str], objective: str) -> dict[str, float]:
        scores: dict[str, float] = {}
        for action in moves:
            target = target_for(action, context)
            if target is None:
                continue
            features = action_features(action, context)
            safe_now, safe_soon, mobility = features[1], features[2], features[3]
            if objective == "item":
                objective_gain = distance_progress(context.current, target, context.items)
            elif objective == "center":
                objective_gain = features[6]
            else:
                objective_gain = 1.6 * distance_progress(
                    context.current, target, context.opponents
                )
            scores[action] = 3.0 * safe_now + safe_soon + objective_gain + 0.4 * mobility
        return scores or {safest_action(context): 0.0}
