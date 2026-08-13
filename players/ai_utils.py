from __future__ import annotations

"""Funções compartilhadas pelos quatro agentes didáticos.

O motor entrega apenas uma observação serializável. Este módulo transforma essa
observação em atributos numéricos simples, mas não escolhe a ação de nenhum
jogador. Cada arquivo ``player_N.py`` contém seu próprio modelo e sua própria
função ``decide``.
"""

from collections import deque
from dataclasses import dataclass
import math
from typing import Iterable

ACTIONS = ("WAIT", "UP", "DOWN", "LEFT", "RIGHT", "BOMB")
MOVE_ACTIONS = ("UP", "DOWN", "LEFT", "RIGHT")
DELTAS = {
    "WAIT": (0, 0),
    "UP": (0, -1),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
    "RIGHT": (1, 0),
}


@dataclass(frozen=True)
class Context:
    board: list[list[str]]
    current: tuple[int, int]
    opponents: tuple[tuple[int, int], ...]
    items: tuple[tuple[int, int], ...]
    bombs: tuple[dict, ...]
    bomb_positions: frozenset[tuple[int, int]]
    flames: frozenset[tuple[int, int]]
    danger_now: frozenset[tuple[int, int]]
    danger_soon: frozenset[tuple[int, int]]
    bomb_available: bool
    bomb_range: int
    shrink: dict


def build_context(observation: dict) -> Context:
    me = observation["self"]
    board = observation["board"]
    bombs = tuple(observation.get("bombs", ()))
    flames = frozenset((f["x"], f["y"]) for f in observation.get("flames", ()))
    bomb_positions = frozenset((b["x"], b["y"]) for b in bombs)
    danger_now, danger_soon = danger_maps(board, bombs, flames)
    current = (me["x"], me["y"])
    opponents = tuple(
        (p["x"], p["y"])
        for p in observation.get("players", ())
        if p["id"] != me["id"] and p["alive"]
    )
    items = tuple((item["x"], item["y"]) for item in observation.get("items", ()))
    return Context(
        board=board,
        current=current,
        opponents=opponents,
        items=items,
        bombs=bombs,
        bomb_positions=bomb_positions,
        flames=flames,
        danger_now=frozenset(danger_now),
        danger_soon=frozenset(danger_soon),
        bomb_available=(
            me["active_bombs"] < me["max_bombs"] and current not in bomb_positions
        ),
        bomb_range=int(me["bomb_range"]),
        shrink=observation.get("shrink", {}),
    )


def in_bounds(pos: tuple[int, int], board: list[list[str]]) -> bool:
    x, y = pos
    return 0 <= y < len(board) and 0 <= x < len(board[0])


def walkable(
    pos: tuple[int, int],
    board: list[list[str]],
    bomb_positions: Iterable[tuple[int, int]],
) -> bool:
    if not in_bounds(pos, board):
        return False
    x, y = pos
    return board[y][x] == "." and pos not in bomb_positions


def target_for(action: str, context: Context) -> tuple[int, int] | None:
    if action == "BOMB":
        return context.current if context.bomb_available else None
    dx, dy = DELTAS[action]
    target = (context.current[0] + dx, context.current[1] + dy)
    if action == "WAIT":
        return target
    return target if walkable(target, context.board, context.bomb_positions) else None


def legal_actions(context: Context) -> list[str]:
    result = ["WAIT"]
    for action in MOVE_ACTIONS:
        if target_for(action, context) is not None:
            result.append(action)
    if context.bomb_available:
        result.append("BOMB")
    return result


def blast_cells(
    origin: tuple[int, int], blast_range: int, board: list[list[str]]
) -> set[tuple[int, int]]:
    result = {origin}
    ox, oy = origin
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for distance in range(1, blast_range + 1):
            pos = (ox + dx * distance, oy + dy * distance)
            if not in_bounds(pos, board):
                break
            x, y = pos
            cell = board[y][x]
            if cell in ("#", "X"):
                break
            result.add(pos)
            if cell == "+":
                break
    return result


def danger_maps(
    board: list[list[str]], bombs: Iterable[dict], flames: Iterable[tuple[int, int]]
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    immediate = set(flames)
    soon = set(flames)
    for bomb in bombs:
        cells = blast_cells((bomb["x"], bomb["y"]), int(bomb["range"]), board)
        soon.update(cells)
        if int(bomb["timer"]) <= 3:
            immediate.update(cells)
    return immediate, soon


def nearest_distance(
    origin: tuple[int, int], targets: Iterable[tuple[int, int]]
) -> float:
    target_list = tuple(targets)
    if not target_list:
        return 0.0
    return float(min(abs(origin[0] - x) + abs(origin[1] - y) for x, y in target_list))


def distance_progress(
    before: tuple[int, int], after: tuple[int, int], targets: Iterable[tuple[int, int]]
) -> float:
    target_list = tuple(targets)
    if not target_list:
        return 0.0
    return nearest_distance(before, target_list) - nearest_distance(after, target_list)


def mobility(pos: tuple[int, int], context: Context) -> float:
    free = 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if walkable((pos[0] + dx, pos[1] + dy), context.board, context.bomb_positions):
            free += 1
    return free / 4.0


def center_progress(before: tuple[int, int], after: tuple[int, int], board) -> float:
    center = ((len(board[0]) - 1) / 2.0, (len(board) - 1) / 2.0)

    def distance(pos: tuple[int, int]) -> float:
        return abs(pos[0] - center[0]) + abs(pos[1] - center[1])

    return distance(before) - distance(after)


def adjacent_crate(pos: tuple[int, int], board: list[list[str]]) -> bool:
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        x, y = pos[0] + dx, pos[1] + dy
        if in_bounds((x, y), board) and board[y][x] == "+":
            return True
    return False


def escape_exists_after_bomb(context: Context, max_depth: int = 5) -> bool:
    """Verifica se há uma rota curta para fora do alcance da própria bomba."""
    blast = blast_cells(context.current, context.bomb_range, context.board)
    blocked = set(context.bomb_positions)
    blocked.add(context.current)
    queue = deque([(context.current, 0)])
    visited = {context.current}

    while queue:
        pos, depth = queue.popleft()
        if depth > 0 and pos not in blast and pos not in context.danger_now:
            return True
        if depth >= max_depth:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (pos[0] + dx, pos[1] + dy)
            if nxt in visited:
                continue
            # O jogador pode sair da célula da bomba recém-colocada, mas não voltar.
            if nxt == context.current or walkable(nxt, context.board, blocked):
                visited.add(nxt)
                queue.append((nxt, depth + 1))
    return False


def action_features(action: str, context: Context) -> tuple[float, ...]:
    """Atributos normalizados de uma ação candidata.

    Ordem:
      0 bias
      1 segurança imediata
      2 segurança futura
      3 mobilidade
      4 progresso até item
      5 progresso até oponente
      6 progresso até o centro
      7 valor da bomba contra caixa
      8 valor da bomba contra oponente
      9 rota de fuga após bomba
     10 indicador de espera
     11 indicador de bomba
    """
    target = target_for(action, context)
    if target is None:
        return (1.0, -1.0, -1.0, 0.0, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    safe_now = 1.0 if target not in context.danger_now else -1.0
    safe_soon = 1.0 if target not in context.danger_soon else -1.0
    item_progress = math.tanh(distance_progress(context.current, target, context.items))
    enemy_progress = math.tanh(distance_progress(context.current, target, context.opponents))
    toward_center = math.tanh(center_progress(context.current, target, context.board))

    crate_value = 0.0
    enemy_value = 0.0
    escape_value = 1.0
    if action == "BOMB":
        blast = blast_cells(context.current, context.bomb_range, context.board)
        crate_value = 1.0 if any(context.board[y][x] == "+" for x, y in blast) else 0.0
        enemy_value = 1.0 if any(pos in blast for pos in context.opponents) else 0.0
        escape_value = 1.0 if escape_exists_after_bomb(context) else -1.0

    return (
        1.0,
        safe_now,
        safe_soon,
        mobility(target, context),
        item_progress,
        enemy_progress,
        toward_center,
        crate_value,
        enemy_value,
        escape_value,
        1.0 if action == "WAIT" else 0.0,
        1.0 if action == "BOMB" else 0.0,
    )



def _escape_candidate_score(
    pos: tuple[int, int],
    depth: int,
    context: Context,
    preference: str,
) -> tuple[float, ...]:
    """Pontua uma célula segura conforme a personalidade do agente."""
    distance_from_danger = nearest_distance(pos, context.danger_soon)
    base = (
        float(pos not in context.danger_now),
        float(pos not in context.danger_soon),
    )
    if preference == "aggressive":
        personality = -nearest_distance(pos, context.opponents)
    elif preference == "collector":
        personality = -nearest_distance(pos, context.items)
    elif preference == "territorial":
        center = ((len(context.board[0]) - 1) / 2.0, (len(context.board) - 1) / 2.0)
        personality = -(abs(pos[0] - center[0]) + abs(pos[1] - center[1]))
    else:  # safest
        personality = distance_from_danger
    return base + (-float(depth), personality, mobility(pos, context))


def emergency_escape_action(
    context: Context,
    preference: str = "safest",
    rng=None,
) -> str | None:
    """Escolhe uma rota de fuga curta, mas coerente com o perfil do agente.

    ``safest`` maximiza distância do perigo; ``aggressive`` tenta permanecer
    próximo dos adversários; ``collector`` favorece itens; ``territorial``
    favorece o centro. Quando um gerador aleatório é fornecido, vizinhos e
    empates equivalentes são embaralhados de forma reproduzível pela seed.
    """
    if context.current not in context.danger_now and context.current not in context.danger_soon:
        return None

    reverse_action = {delta: action for action, delta in DELTAS.items() if action in MOVE_ACTIONS}
    queue = deque([(context.current, None, 0)])
    visited = {context.current}
    safe_candidates: list[tuple[tuple[float, ...], str]] = []
    fallback_candidates: list[tuple[tuple[float, ...], str]] = []

    while queue:
        pos, first_action, depth = queue.popleft()
        if depth >= 8:
            continue
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if rng is not None:
            rng.shuffle(directions)
        for dx, dy in directions:
            nxt = (pos[0] + dx, pos[1] + dy)
            if nxt in visited or nxt in context.flames:
                continue
            if not walkable(nxt, context.board, context.bomb_positions):
                continue
            action = first_action or reverse_action[(dx, dy)]
            visited.add(nxt)
            next_depth = depth + 1
            queue.append((nxt, action, next_depth))
            score = _escape_candidate_score(nxt, next_depth, context, preference)
            fallback_candidates.append((score, action))
            if nxt not in context.danger_now and nxt not in context.danger_soon:
                safe_candidates.append((score, action))

    candidates = safe_candidates or fallback_candidates
    if not candidates:
        return "WAIT"
    best_score = max(score for score, _ in candidates)
    best_actions = sorted({action for score, action in candidates if score == best_score})
    return rng.choice(best_actions) if rng is not None else best_actions[0]


def exploration_actions(context: Context, include_bomb: bool = True) -> list[str]:
    """Ações válidas para exploração sem suicídio deliberado."""
    choices: list[str] = []
    for action in legal_actions(context):
        target = target_for(action, context)
        if target is None:
            continue
        if action == "BOMB":
            if include_bomb and escape_exists_after_bomb(context):
                choices.append(action)
            continue
        if (
            target not in context.danger_now
            and target not in context.danger_soon
            and target not in context.flames
        ):
            choices.append(action)
    return choices or ["WAIT"]


def choose_scored_action(
    scores: dict[str, float],
    context: Context,
    rng,
    exploration_rate: float,
    tie_tolerance: float = 1e-9,
    include_bomb_exploration: bool = True,
) -> str:
    """Aplica exploração controlada e desempate aleatório reproduzível."""
    if not scores:
        return safest_action(context)
    if rng.random() < exploration_rate:
        return rng.choice(exploration_actions(context, include_bomb_exploration))
    best_score = max(scores.values())
    best_actions = [
        action for action, score in scores.items()
        if abs(score - best_score) <= tie_tolerance
    ]
    return rng.choice(best_actions)


def safest_action(context: Context, prefer_items: bool = True) -> str:
    """Fallback determinístico usado quando o modelo empata ou não encontra opção."""
    best_action = "WAIT"
    best_key = (-99.0, -99.0, -99.0, -99.0)
    for action in legal_actions(context):
        if action == "BOMB":
            continue
        target = target_for(action, context)
        assert target is not None
        key = (
            float(target not in context.danger_now),
            float(target not in context.danger_soon),
            mobility(target, context),
            distance_progress(context.current, target, context.items) if prefer_items else 0.0,
        )
        if key > best_key:
            best_key = key
            best_action = action
    return best_action
