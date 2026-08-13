from __future__ import annotations

import importlib

from main import DEFAULT_AGENTS, build_parser


def test_default_execution_loads_four_players():
    args = build_parser().parse_args([])
    assert args.agents == [
        "players.player_1:Agent",
        "players.player_2:Agent",
        "players.player_3:Agent",
        "players.player_4:Agent",
    ]
    assert args.agents == DEFAULT_AGENTS


def test_each_player_declares_own_decide_method():
    classes = []
    for number in range(1, 5):
        module = importlib.import_module(f"players.player_{number}")
        classes.append(module.Agent)
        assert "decide" in module.Agent.__dict__
    assert len(set(classes)) == 4
