from __future__ import annotations

import argparse
import csv
import itertools
from dataclasses import dataclass, field
from pathlib import Path

from bomberman.agent_runtime import AgentController
from bomberman.config import GameConfig
from bomberman.engine import GameEngine


@dataclass(slots=True)
class Record:
    agent: str
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    tournament_points: int = 0
    game_score: int = 0
    kills: int = 0
    items: int = 0
    faults: int = 0
    opponents: set[str] = field(default_factory=set)


def short_name(spec: str) -> str:
    return spec.split(":", 1)[0].rsplit(".", 1)[-1]


def play_match(agent_specs: list[str], seed: int, config: GameConfig) -> dict:
    names = [short_name(spec) for spec in agent_specs]
    engine = GameEngine(names, seed=seed, config=config)
    controllers: dict[int, AgentController] = {}
    try:
        for pid, spec in enumerate(agent_specs):
            controllers[pid] = AgentController(
                spec=spec,
                player_id=pid,
                seed=seed,
                timeout_ms=config.agent_timeout_ms,
            )
        while not engine.game_over:
            actions = {
                p.player_id: controllers[p.player_id].decide(engine.observation_for(p.player_id))
                for p in engine.alive_players()
            }
            engine.step(actions)

        assert engine.result is not None
        return {
            "winner_ids": engine.result.winner_ids,
            "standings": engine.result.standings,
            "faults": {pid: controller.stats.faults for pid, controller in controllers.items()},
            "ticks": engine.result.ticks,
            "reason": engine.result.reason,
        }
    finally:
        for controller in controllers.values():
            controller.close()


def run_tournament(agent_specs: list[str], rounds: int, base_seed: int, output: Path) -> None:
    if len(agent_specs) < 2:
        raise SystemExit("Informe pelo menos dois agentes.")
    if len(set(agent_specs)) != len(agent_specs):
        raise SystemExit("Cada especificação de agente deve ser única no torneio.")

    config = GameConfig(
        max_ticks=8 * 120,
        shrink_start_tick=8 * 55,
        shrink_interval_ticks=8 * 6,
        agent_timeout_ms=80,
    )
    records = {spec: Record(agent=spec) for spec in agent_specs}
    match_index = 0

    # Todos contra todos em duelos, com ida e volta para reduzir viés de posição.
    for first, second in itertools.combinations(agent_specs, 2):
        records[first].opponents.add(second)
        records[second].opponents.add(first)
        for round_index in range(rounds):
            for leg in range(2):
                ordered = [first, second] if leg == 0 else [second, first]
                seed = base_seed + match_index * 1009 + round_index
                match_index += 1
                result = play_match(ordered, seed=seed, config=config)

                for pid, spec in enumerate(ordered):
                    row = next(item for item in result["standings"] if item["player_id"] == pid)
                    record = records[spec]
                    record.played += 1
                    record.game_score += row["score"]
                    record.kills += row["kills"]
                    record.items += row["items"]
                    record.faults += result["faults"][pid]

                winners = result["winner_ids"]
                if len(winners) == 1:
                    winner_spec = ordered[winners[0]]
                    loser_spec = ordered[1 - winners[0]]
                    records[winner_spec].wins += 1
                    records[winner_spec].tournament_points += 3
                    records[loser_spec].losses += 1
                else:
                    for spec in ordered:
                        records[spec].draws += 1
                        records[spec].tournament_points += 1

                print(
                    f"Partida {match_index:03d}: {short_name(ordered[0])} x "
                    f"{short_name(ordered[1])} | vencedores={winners} | seed={seed}"
                )

    ordered_records = sorted(
        records.values(),
        key=lambda r: (-r.tournament_points, -r.wins, -r.game_score, r.faults, r.agent),
    )
    max_points = max((record.tournament_points for record in ordered_records), default=1)

    fieldnames = [
        "rank",
        "agent",
        "played",
        "wins",
        "draws",
        "losses",
        "tournament_points",
        "performance_0_10",
        "game_score",
        "kills",
        "items",
        "faults",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for rank, record in enumerate(ordered_records, start=1):
            performance = 10.0 * record.tournament_points / max(1, max_points)
            writer.writerow(
                {
                    "rank": rank,
                    "agent": record.agent,
                    "played": record.played,
                    "wins": record.wins,
                    "draws": record.draws,
                    "losses": record.losses,
                    "tournament_points": record.tournament_points,
                    "performance_0_10": f"{performance:.2f}",
                    "game_score": record.game_score,
                    "kills": record.kills,
                    "items": record.items,
                    "faults": record.faults,
                }
            )

    print(f"\nRanking salvo em: {output.resolve()}")
    for rank, record in enumerate(ordered_records, start=1):
        print(
            f"{rank:2d}. {short_name(record.agent):24s} "
            f"pts={record.tournament_points:3d} V={record.wins:2d} "
            f"E={record.draws:2d} D={record.losses:2d} faults={record.faults}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Torneio todos-contra-todos de agentes")
    parser.add_argument("agents", nargs="+", help="Agentes no formato pacote.modulo:Classe")
    parser.add_argument("--rounds", type=int, default=3, help="Rodadas por confronto e por posição")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path, default=Path("leaderboard.csv"))
    args = parser.parse_args()
    run_tournament(args.agents, args.rounds, args.seed, args.output)


if __name__ == "__main__":
    main()
