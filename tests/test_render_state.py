from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from bomberman.config import GameConfig
from bomberman.engine import GameEngine
from bomberman.enums import Action, Tile
from bomberman.render_state import VisualTransition, capture_snapshot
from bomberman.state import Bomb


class RenderStateTests(unittest.TestCase):
    def make_engine(self) -> GameEngine:
        config = GameConfig(
            width=15,
            height=13,
            crate_density=0.0,
            item_probability=0.0,
            shrink_start_tick=9999,
            max_ticks=9999,
            initial_move_delay=1,
        )
        return GameEngine(["p1", "p2"], seed=11, config=config)

    def test_visual_position_never_changes_logical_state(self):
        engine = self.make_engine()
        engine.players[1].pos = (6, 5)
        before = capture_snapshot(engine)
        engine.step({0: Action.WAIT, 1: Action.LEFT})
        after = capture_snapshot(engine)
        transition = VisualTransition(before, after, tuple(engine.events))

        logical_position = engine.players[1].pos
        visual_position = transition.player_position(1, 0.25)
        self.assertEqual(logical_position, (5, 5))
        self.assertNotEqual(visual_position, logical_position)
        self.assertEqual(engine.players[1].pos, logical_position)

    def test_player_reaches_damage_cell_before_visual_elimination(self):
        engine = self.make_engine()
        # Limpa obstáculos locais para tornar o cenário inequívoco.
        for x in range(3, 8):
            engine.grid[5][x] = Tile.FLOOR
        engine.players[0].pos = (3, 5)
        engine.players[1].pos = (6, 5)
        engine.bombs[1] = Bomb(
            bomb_id=1,
            owner_id=0,
            x=4,
            y=5,
            explode_tick=1,
            blast_range=2,
        )
        engine.players[0].active_bombs = 1
        engine.next_bomb_id = 2

        before = capture_snapshot(engine)
        engine.step({0: Action.WAIT, 1: Action.LEFT})
        after = capture_snapshot(engine)
        transition = VisualTransition(before, after, tuple(engine.events))

        event = transition.elimination_for(1)
        self.assertIsNotNone(event)
        self.assertEqual(event["position"], (5, 5))
        self.assertEqual(event["bomb_id"], 1)
        self.assertEqual(event["bomb_position"], (4, 5))
        self.assertTrue(transition.player_visible(1, 0.50))
        self.assertEqual(transition.player_position(1, 0.60), (5.0, 5.0))
        self.assertFalse(transition.player_visible(1, 0.80))

    def test_event_history_is_auditable(self):
        engine = self.make_engine()
        engine.step({0: Action.BOMB, 1: Action.WAIT})
        self.assertTrue(engine.event_history)
        event = engine.event_history[0]
        self.assertEqual(event["type"], "bomb_placed")
        self.assertEqual(event["tick"], 1)
        self.assertEqual(event["event_id"], 1)
        self.assertIn("bomb_id", event)

    def test_sprite_sheets_have_expected_frame_counts(self):
        root = Path(__file__).resolve().parents[1] / "assets" / "sheets"
        for player in range(1, 5):
            with Image.open(root / f"player_{player}.png") as image:
                self.assertEqual(image.size, (32 * 12, 32))
        with Image.open(root / "bomb.png") as image:
            self.assertEqual(image.size, (32 * 3, 32))
        with Image.open(root / "flames.png") as image:
            self.assertEqual(image.size, (32 * 14, 32))


if __name__ == "__main__":
    unittest.main()
