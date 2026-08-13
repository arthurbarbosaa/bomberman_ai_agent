from __future__ import annotations

import math
import random
from collections import deque

from .base_agent import BaseAgent


DIRECTIONS = {
    "WAIT": (0, 0),
    "UP": (0, -1),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
    "RIGHT": (1, 0),
}


class Agent(BaseAgent):
    """Exemplo de agente baseado em um modelo linear de política.

    Para cada ação, o agente extrai atributos do estado e calcula
        score(ação) = soma_i peso_i * atributo_i.
    Os alunos podem aprender os pesos com regressão, algoritmo genético,
    evolução diferencial, aprendizagem por reforço ou substituir o modelo.
    """

    def __init__(self, player_id: int = 0, seed: int = 0) -> None:
        super().__init__(player_id, seed)
        self.rng = random.Random(seed + 7919 * player_id)
        self.weights = {
            "bias": 0.10,
            "immediate_danger": -12.0,
            "future_danger": -5.5,
            "mobility": 1.10,
            "item_progress": 2.20,
            "enemy_progress": 0.25,
            "shrink_safety": 1.50,
            "bomb_near_crate": 2.80,
            "bomb_near_enemy": 4.20,
            "bomb_trap_risk": -9.0,
            "wait_penalty": -0.35,
        }

    def decide(self, observation: dict) -> str:
        me = observation["self"]
        if not me["alive"]:
            return "WAIT"

        board = observation["board"]
        bombs = observation["bombs"]
        flames = {(f["x"], f["y"]) for f in observation["flames"]}
        bomb_positions = {(b["x"], b["y"]) for b in bombs}
        opponents = [
            (p["x"], p["y"])
            for p in observation["players"]
            if p["id"] != me["id"] and p["alive"]
        ]
        items = [(i["x"], i["y"]) for i in observation["items"]]
        current = (me["x"], me["y"])
        danger_now, danger_soon = self._danger_maps(board, bombs, flames)

        candidates = list(DIRECTIONS)
        if me["active_bombs"] < me["max_bombs"] and current not in bomb_positions:
            candidates.append("BOMB")

        scored: list[tuple[float, str]] = []
        for action in candidates:
            features = self._features(
                action=action,
                current=current,
                board=board,
                bomb_positions=bomb_positions,
                danger_now=danger_now,
                danger_soon=danger_soon,
                items=items,
                opponents=opponents,
                bomb_range=me["bomb_range"],
                shrink=observation["shrink"],
            )
            score = sum(self.weights[key] * value for key, value in features.items())
            score += self.rng.random() * 1e-4  # desempate reprodutível
            scored.append((score, action))

        scored.sort(reverse=True)
        return scored[0][1]

    def _features(
        self,
        action: str,
        current: tuple[int, int],
        board: list[list[str]],
        bomb_positions: set[tuple[int, int]],
        danger_now: set[tuple[int, int]],
        danger_soon: set[tuple[int, int]],
        items: list[tuple[int, int]],
        opponents: list[tuple[int, int]],
        bomb_range: int,
        shrink: dict,
    ) -> dict[str, float]:
        target = current
        if action in DIRECTIONS:
            dx, dy = DIRECTIONS[action]
            proposed = (current[0] + dx, current[1] + dy)
            if self._walkable(proposed, board, bomb_positions):
                target = proposed
            elif action != "WAIT":
                return {
                    "bias": 1.0,
                    "immediate_danger": 1.0,
                    "future_danger": 1.0,
                    "mobility": 0.0,
                    "item_progress": -2.0,
                    "enemy_progress": -2.0,
                    "shrink_safety": -2.0,
                    "bomb_near_crate": 0.0,
                    "bomb_near_enemy": 0.0,
                    "bomb_trap_risk": 1.0,
                    "wait_penalty": 0.0,
                }

        mobility = sum(
            self._walkable((target[0] + dx, target[1] + dy), board, bomb_positions)
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
        ) / 4.0

        item_progress = self._distance_progress(current, target, items)
        enemy_progress = self._distance_progress(current, target, opponents)
        shrink_safety = self._shrink_safety(target, board, shrink)

        bomb_near_crate = 0.0
        bomb_near_enemy = 0.0
        bomb_trap_risk = 0.0
        if action == "BOMB":
            blast = self._blast_cells(current, bomb_range, board)
            bomb_near_crate = float(any(board[y][x] == "+" for x, y in blast))
            bomb_near_enemy = float(any(pos in blast for pos in opponents))
            bomb_trap_risk = float(not self._escape_exists(current, board, bomb_positions | {current}, blast))

        return {
            "bias": 1.0,
            "immediate_danger": float(target in danger_now),
            "future_danger": float(target in danger_soon),
            "mobility": mobility,
            "item_progress": item_progress,
            "enemy_progress": enemy_progress,
            "shrink_safety": shrink_safety,
            "bomb_near_crate": bomb_near_crate,
            "bomb_near_enemy": bomb_near_enemy,
            "bomb_trap_risk": bomb_trap_risk,
            "wait_penalty": float(action == "WAIT"),
        }

    @staticmethod
    def _walkable(
        pos: tuple[int, int], board: list[list[str]], bomb_positions: set[tuple[int, int]]
    ) -> bool:
        x, y = pos
        return (
            0 <= y < len(board)
            and 0 <= x < len(board[0])
            and board[y][x] == "."
            and pos not in bomb_positions
        )

    def _danger_maps(self, board, bombs, flames):
        immediate = set(flames)
        soon = set(flames)
        for bomb in bombs:
            cells = self._blast_cells((bomb["x"], bomb["y"]), bomb["range"], board)
            soon.update(cells)
            if bomb["timer"] <= 3:
                immediate.update(cells)
        return immediate, soon

    @staticmethod
    def _blast_cells(origin: tuple[int, int], blast_range: int, board: list[list[str]]):
        result = {origin}
        ox, oy = origin
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            for distance in range(1, blast_range + 1):
                x, y = ox + dx * distance, oy + dy * distance
                if board[y][x] in ("#", "X"):
                    break
                result.add((x, y))
                if board[y][x] == "+":
                    break
        return result

    @staticmethod
    def _nearest_distance(origin: tuple[int, int], targets: list[tuple[int, int]]) -> float:
        if not targets:
            return 0.0
        return float(min(abs(origin[0] - x) + abs(origin[1] - y) for x, y in targets))

    def _distance_progress(self, before, after, targets) -> float:
        if not targets:
            return 0.0
        return self._nearest_distance(before, targets) - self._nearest_distance(after, targets)

    @staticmethod
    def _shrink_safety(target, board, shrink) -> float:
        x, y = target
        distance_to_border = min(x, y, len(board[0]) - 1 - x, len(board) - 1 - y)
        urgency = 1.0 if shrink["active"] or (shrink["ticks_to_next"] or 9999) < 40 else 0.2
        return urgency * math.tanh(distance_to_border / 3.0)

    def _escape_exists(self, start, board, bomb_positions, forbidden) -> bool:
        queue = deque([(start, 0)])
        visited = {start}
        while queue:
            pos, distance = queue.popleft()
            if distance >= 3 and pos not in forbidden:
                return True
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nxt = (pos[0] + dx, pos[1] + dy)
                if nxt in visited:
                    continue
                if nxt == start or self._walkable(nxt, board, bomb_positions):
                    visited.add(nxt)
                    queue.append((nxt, distance + 1))
        return False
