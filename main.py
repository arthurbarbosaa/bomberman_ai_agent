from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path

from bomberman.agent_runtime import AgentController
from bomberman.config import GameConfig
from bomberman.engine import GameEngine
from bomberman.renderer import run_visual


DEFAULT_AGENTS = [
    "players.player_1:Agent",
    "players.player_2:Agent",
    "players.player_3:Agent",
    "players.player_4:Agent",
]


def _display_name(spec: str) -> str:
    module = spec.split(":", 1)[0]
    return module.rsplit(".", 1)[-1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Arena Bomberman para agentes de IA")
    parser.add_argument(
        "--agents",
        nargs="+",
        default=DEFAULT_AGENTS.copy(),
        help=(
            "Agentes no formato pacote.modulo:Classe. Sem este argumento, "
            "os quatro arquivos players/player_1.py a player_4.py são carregados."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Seed da partida. Quando omitida, uma nova seed é gerada; informe um "
            "valor para reproduzir exatamente a mesma partida."
        ),
    )
    parser.add_argument("--headless", action="store_true", help="Executa sem janela gráfica")
    parser.add_argument(
        "--tick-rate",
        "--fps",
        dest="tick_rate",
        type=int,
        default=8,
        help="Ticks lógicos por segundo; --fps é mantido como alias legado",
    )
    parser.add_argument(
        "--render-fps",
        type=int,
        default=60,
        help="Quadros por segundo apenas para animação; não altera a lógica",
    )
    parser.add_argument("--width", type=int, default=15)
    parser.add_argument("--height", type=int, default=13)
    parser.add_argument("--timeout-ms", type=int, default=80)
    parser.add_argument("--shrink-after", type=float, default=75.0, help="Segundos até iniciar o fechamento")
    parser.add_argument("--max-seconds", type=float, default=150.0)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument(
        "--event-log",
        type=Path,
        default=None,
        help="Salva o histórico auditável de eventos da partida em JSON",
    )
    return parser


def resolve_seed(seed: int | None) -> int:
    """Retorna a seed informada ou gera uma seed imprevisível para a partida."""
    return seed if seed is not None else secrets.randbits(31)


def run(args: argparse.Namespace) -> dict:
    if not 2 <= len(args.agents) <= 4:
        raise SystemExit("Use de 2 a 4 agentes por partida.")

    match_seed = resolve_seed(args.seed)
    print(f"[PARTIDA] seed={match_seed}")

    config = GameConfig(
        width=args.width,
        height=args.height,
        ticks_per_second=args.tick_rate,
        shrink_start_tick=max(1, int(args.shrink_after * args.tick_rate)),
        shrink_interval_ticks=max(1, int(7 * args.tick_rate)),
        max_ticks=max(1, int(args.max_seconds * args.tick_rate)),
        agent_timeout_ms=args.timeout_ms,
    )
    names = [_display_name(spec) for spec in args.agents]
    engine = GameEngine(names, seed=match_seed, config=config)
    controllers: dict[int, AgentController] = {}

    try:
        for player_id, spec in enumerate(args.agents):
            controller = AgentController(
                spec=spec,
                player_id=player_id,
                seed=match_seed,
                timeout_ms=config.agent_timeout_ms,
            )
            controllers[player_id] = controller
            if controller.load_error:
                print(f"[ERRO] Agente P{player_id + 1} ({spec}) não carregou:\n{controller.load_error}")

        if args.headless:
            while not engine.game_over:
                actions = {
                    player.player_id: controllers[player.player_id].decide(
                        engine.observation_for(player.player_id)
                    )
                    for player in engine.alive_players()
                }
                engine.step(actions)
        else:
            run_visual(engine, controllers, render_fps=args.render_fps)

        if engine.result is None:
            # Pode ocorrer quando o usuário fecha a janela antes do fim.
            result = {
                "seed": match_seed,
                "interrupted": True,
                "tick": engine.tick,
                "standings": [],
            }
        else:
            result = {
                "seed": match_seed,
                "reason": engine.result.reason,
                "ticks": engine.result.ticks,
                "winner_ids": engine.result.winner_ids,
                "standings": engine.result.standings,
                "agent_faults": {
                    str(pid): {
                        "timeouts": controller.stats.timeouts,
                        "errors": controller.stats.errors,
                        "invalid_actions": controller.stats.invalid_actions,
                    }
                    for pid, controller in controllers.items()
                },
            }

        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.json_output:
            args.json_output.parent.mkdir(parents=True, exist_ok=True)
            args.json_output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        if args.event_log:
            args.event_log.parent.mkdir(parents=True, exist_ok=True)
            args.event_log.write_text(
                json.dumps(engine.event_history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return result
    finally:
        for controller in controllers.values():
            controller.close()


def main() -> None:
    parser = build_parser()
    run(parser.parse_args())


if __name__ == "__main__":
    main()
