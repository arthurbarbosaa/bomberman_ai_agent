from __future__ import annotations

import importlib
import multiprocessing as mp
import traceback
from dataclasses import dataclass
from typing import Any

from .enums import Action


def _load_agent(spec: str, player_id: int, seed: int) -> Any:
    module_name, separator, class_name = spec.partition(":")
    if not separator:
        class_name = "Agent"
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)

    # Aceita construtores progressivamente mais simples.
    for kwargs in (
        {"player_id": player_id, "seed": seed},
        {"seed": seed},
        {},
    ):
        try:
            return cls(**kwargs)
        except TypeError:
            continue
    return cls()


def _agent_worker(connection, spec: str, player_id: int, seed: int) -> None:
    try:
        agent = _load_agent(spec, player_id, seed)
        if hasattr(agent, "reset"):
            agent.reset(player_id=player_id, seed=seed)
        connection.send({"status": "ready"})
    except Exception:
        connection.send({"status": "load_error", "traceback": traceback.format_exc()})
        connection.close()
        return

    while True:
        try:
            message = connection.recv()
        except EOFError:
            break
        command = message.get("command")
        if command == "close":
            break
        if command != "decide":
            continue
        try:
            action = agent.decide(message["observation"])
            if isinstance(action, Action):
                action = action.value
            connection.send({"status": "ok", "action": str(action).upper()})
        except Exception:
            connection.send({"status": "error", "traceback": traceback.format_exc()})
    connection.close()


@dataclass(slots=True)
class AgentStats:
    timeouts: int = 0
    errors: int = 0
    invalid_actions: int = 0

    @property
    def faults(self) -> int:
        return self.timeouts + self.errors + self.invalid_actions


class AgentController:
    """Executa um agente em processo separado e limita o tempo de cada decisão.

    Isto evita que um loop infinito no agente congele a partida. Não é um sandbox
    de segurança completo; para códigos não confiáveis, use contêiner/VM.
    """

    def __init__(
        self,
        spec: str,
        player_id: int,
        seed: int,
        timeout_ms: int,
    ) -> None:
        self.spec = spec
        self.player_id = player_id
        self.seed = seed
        self.timeout_seconds = timeout_ms / 1000.0
        self.stats = AgentStats()
        self.load_error: str | None = None

        context = mp.get_context("spawn")
        self.parent_connection, child_connection = context.Pipe()
        self.process = context.Process(
            target=_agent_worker,
            args=(child_connection, spec, player_id, seed),
            daemon=True,
        )
        self.process.start()
        if self.parent_connection.poll(4.0):
            response = self.parent_connection.recv()
            if response.get("status") != "ready":
                self.load_error = response.get("traceback", "Falha ao carregar o agente.")
        else:
            self.load_error = "Timeout ao carregar o agente."

    def decide(self, observation: dict) -> str:
        if self.load_error or not self.process.is_alive():
            self.stats.errors += 1
            return Action.WAIT.value
        try:
            self.parent_connection.send({"command": "decide", "observation": observation})
        except (BrokenPipeError, EOFError, OSError):
            self.stats.errors += 1
            return Action.WAIT.value

        if not self.parent_connection.poll(self.timeout_seconds):
            self.stats.timeouts += 1
            self._terminate()
            return Action.WAIT.value

        try:
            response = self.parent_connection.recv()
        except (EOFError, OSError):
            self.stats.errors += 1
            return Action.WAIT.value

        if response.get("status") != "ok":
            self.stats.errors += 1
            return Action.WAIT.value

        action = response.get("action", Action.WAIT.value)
        if action not in {item.value for item in Action}:
            self.stats.invalid_actions += 1
            return Action.WAIT.value
        return action

    def _terminate(self) -> None:
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=0.5)

    def close(self) -> None:
        if self.process.is_alive():
            try:
                self.parent_connection.send({"command": "close"})
            except (BrokenPipeError, EOFError, OSError):
                pass
            self.process.join(timeout=0.5)
        self._terminate()
        try:
            self.parent_connection.close()
        except OSError:
            pass
