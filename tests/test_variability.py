from __future__ import annotations

from unittest.mock import patch

from bomberman.config import GameConfig
from bomberman.engine import GameEngine
from main import build_parser, resolve_seed
from players.agent_config import PLAYER_PROFILES


def _action_trace(module_name: str, player_id: int, seed: int, steps: int = 12):
    module = __import__(module_name, fromlist=["Agent"])
    engine = GameEngine(
        ["p1", "p2", "p3", "p4"],
        seed=seed,
        config=GameConfig(max_ticks=100),
    )
    agent = module.Agent(player_id=player_id, seed=seed)
    trace = []
    for _ in range(steps):
        action = agent.decide(engine.observation_for(player_id))
        trace.append(action)
        engine.step({player_id: action})
        if engine.game_over or not engine.players[player_id].alive:
            break
    return trace


def test_seed_is_automatic_by_default_and_fixed_when_requested():
    assert build_parser().parse_args([]).seed is None
    assert resolve_seed(42) == 42
    with patch("main.secrets.randbits", return_value=123456):
        assert resolve_seed(None) == 123456


def test_profiles_are_distinct():
    names = {profile.name for profile in PLAYER_PROFILES.values()}
    rates = {profile.exploration_rate for profile in PLAYER_PROFILES.values()}
    escapes = {profile.escape_preference for profile in PLAYER_PROFILES.values()}
    assert len(names) == 4
    assert len(rates) == 4
    assert len(escapes) == 4


def test_fixed_seed_reproduces_each_agent_trace():
    for player_id in range(4):
        module = f"players.player_{player_id + 1}"
        assert _action_trace(module, player_id, 8128) == _action_trace(
            module, player_id, 8128
        )
