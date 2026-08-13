from __future__ import annotations

import importlib
import unittest

from bomberman.config import GameConfig
from bomberman.engine import GameEngine


class FourAIPlayersTest(unittest.TestCase):
    MODULES = (
        "players.player_1",
        "players.player_2",
        "players.player_3",
        "players.player_4",
    )

    def test_models_are_distinct_and_return_valid_actions(self) -> None:
        engine = GameEngine(
            ["player_1", "player_2", "player_3", "player_4"],
            seed=42,
            config=GameConfig(),
        )
        model_names = []
        valid = {"WAIT", "UP", "DOWN", "LEFT", "RIGHT", "BOMB"}

        for player_id, module_name in enumerate(self.MODULES):
            module = importlib.import_module(module_name)
            model_names.append(module.MODEL_NAME)
            agent = module.Agent(player_id=player_id, seed=42)
            action = agent.decide(engine.observation_for(player_id))
            self.assertIn(action, valid)

        self.assertEqual(len(set(model_names)), 4)


if __name__ == "__main__":
    unittest.main()
