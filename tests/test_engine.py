from __future__ import annotations

import unittest

from bomberman.config import GameConfig
from bomberman.engine import GameEngine
from bomberman.enums import Action, ItemType, Tile
from bomberman.state import Bomb, Flame, Item


class EngineTests(unittest.TestCase):
    def make_engine(self, **overrides) -> GameEngine:
        values = {
            "width": 15,
            "height": 13,
            "crate_density": 0.45,
            "item_probability": 0.3,
            "shrink_start_tick": 9999,
            "max_ticks": 9999,
        }
        values.update(overrides)
        return GameEngine(["a", "b"], seed=17, config=GameConfig(**values))

    def test_spawn_has_l_shaped_escape_routes(self):
        engine = self.make_engine()
        for player in engine.players.values():
            x, y = player.pos
            dx = 1 if x < engine.width // 2 else -1
            dy = 1 if y < engine.height // 2 else -1
            expected_floor = {
                (x, y),
                (x + dx, y),
                (x + 2 * dx, y),
                (x + 2 * dx, y + dy),
                (x, y + dy),
                (x, y + 2 * dy),
                (x + dx, y + 2 * dy),
            }
            for px, py in expected_floor:
                self.assertEqual(engine.grid[py][px], Tile.FLOOR)

    def test_bomb_becomes_solid_after_owner_leaves(self):
        engine = self.make_engine()
        start = engine.players[0].pos
        engine.step({0: Action.BOMB, 1: Action.WAIT})
        self.assertTrue(engine.is_walkable(start, 0))
        engine.step({0: Action.RIGHT, 1: Action.WAIT})
        self.assertNotEqual(engine.players[0].pos, start)
        self.assertFalse(engine.is_walkable(start, 0))
        self.assertFalse(engine.is_walkable(start, 1))

    def test_curse_transfers_on_orthogonal_contact(self):
        engine = self.make_engine()
        first = engine.players[0]
        second = engine.players[1]
        first.pos = (5, 5)
        second.pos = (6, 5)
        engine.tick = 10
        engine._apply_curse(first)
        first.curse_acquired_tick = 9
        original_mapping = dict(first.curse_mapping or {})
        engine._transmit_curses()
        self.assertFalse(first.cursed)
        self.assertTrue(second.cursed)
        self.assertEqual(second.curse_mapping, original_mapping)

    def test_curse_changes_every_command(self):
        engine = self.make_engine()
        mapping = engine._make_curse_mapping()
        self.assertEqual(set(mapping), set(Action))
        self.assertTrue(all(source != target for source, target in mapping.items()))

    def test_item_changes_player_attribute(self):
        engine = self.make_engine()
        player = engine.players[0]
        engine.items[player.pos] = Item(ItemType.RANGE_UP, player.x, player.y)
        before = player.bomb_range
        engine._collect_items()
        self.assertEqual(player.bomb_range, before + 1)
        self.assertEqual(player.items_collected, 1)

    def test_arena_guarantees_all_item_types(self):
        engine = self.make_engine()
        self.assertTrue(set(ItemType).issubset(set(engine.hidden_items.values())))


    def test_active_flame_blocks_entry_and_prevents_phantom_death(self):
        engine = self.make_engine()
        player = engine.players[1]
        player.pos = (11, 10)
        engine.flames[(11, 11)] = Flame(
            x=11, y=11, expires_tick=10, owner_id=1, created_tick=0
        )
        engine.step({0: Action.WAIT, 1: Action.DOWN})
        self.assertEqual(player.pos, (11, 10))
        self.assertTrue(player.alive)

    def test_player_outside_blast_range_survives(self):
        engine = self.make_engine()
        engine.players[0].pos = (3, 5)
        engine.players[1].pos = (8, 5)
        engine.bombs[1] = Bomb(
            bomb_id=1, owner_id=0, x=5, y=5, explode_tick=1, blast_range=2
        )
        engine.players[0].active_bombs = 1
        engine.next_bomb_id = 2
        engine.step({0: Action.WAIT, 1: Action.WAIT})
        self.assertTrue(engine.players[1].alive)
        self.assertNotIn(engine.players[1].pos, engine.flames)

    def test_elimination_event_reports_direct_blast_and_position(self):
        engine = self.make_engine()
        engine.players[0].pos = (3, 5)
        engine.players[1].pos = (6, 5)
        engine.bombs[1] = Bomb(
            bomb_id=1, owner_id=0, x=5, y=5, explode_tick=1, blast_range=2
        )
        engine.players[0].active_bombs = 1
        engine.next_bomb_id = 2
        engine.step({0: Action.WAIT, 1: Action.WAIT})
        event = next(e for e in engine.events if e["type"] == "player_eliminated")
        self.assertEqual(event["reason"], "bomb_blast")
        self.assertEqual(event["position"], (6, 5))
        self.assertEqual(event["tick"], 1)

    def test_arena_shrink_eliminates_border_players(self):
        engine = self.make_engine(shrink_start_tick=1, shrink_interval_ticks=1)
        engine.step({0: Action.WAIT, 1: Action.WAIT})
        self.assertEqual(engine.shrink_margin, 1)
        self.assertEqual(engine.grid[1][1], Tile.SHRINK_WALL)
        self.assertFalse(engine.players[0].alive)
        self.assertFalse(engine.players[1].alive)


if __name__ == "__main__":
    unittest.main()
