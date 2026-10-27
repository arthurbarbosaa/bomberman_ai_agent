from __future__ import annotations

"""Nosso agente — planejador com simulação temporal do perigo.

Cada decisão segue cinco etapas:

1. Percepção: a observação vira grade, bombas, chamas, itens e oponentes.
2. Linha do tempo do perigo: calcula em que tick cada bomba explode (inclusive
   reações em cadeia), por quantos ticks cada célula fica em chamas e quando
   cada anel da arena se fecha.
3. Filtro de segurança: para cada ação candidata, uma busca em largura no
   espaço (célula, tempo, recarga de movimento) verifica se ainda existe uma
   rota que sobrevive até uma célula definitivamente segura.
4. Utilidade: entre as ações seguras, escolhe a que mais aproxima de objetivos
   (itens, caixas, oponentes encurralados, centro da arena), com desconto pela
   distância.
5. Maldição: aprende a permutação de comandos comparando a ação pretendida e a
   ação efetiva do tick anterior e escolhe o comando que produz a ação desejada.

O arquivo é autocontido: não depende do motor nem de ``players/ai_utils.py``.
"""

import heapq
import random
import time
from collections import deque

ACTIONS = ("WAIT", "UP", "DOWN", "LEFT", "RIGHT", "BOMB")
MOVES = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
INF = 10**9

DECAY = 0.85  # desconto por passo de distância até um objetivo
ESCAPE_GOALS = 3  # células seguras distintas procuradas pela busca de fuga
ESCAPE_NODE_BUDGET = 5000
HORIZON_CAP = 60
# O motor encerra o agente que passar de 80 ms; o orçamento deixa folga para a
# comunicação entre processos e para máquinas mais lentas.
TIME_BUDGET = 0.030
OPP_REACH = 3  # alcance dos oponentes considerado na fuga robusta
THREAT_PENALTY = 60.0  # posição que uma bomba nova de um oponente fecharia
DEAD_END_RADIUS = 6
DEAD_END_PENALTY = 50.0
RING_WINDOW = 32  # anéis que fecham depois disso ficam a cargo dos objetivos


class View:
    """Representação da observação preparada para o planejamento."""

    __slots__ = (
        "tick", "board", "width", "height", "pos", "me", "nm", "delay",
        "can_bomb", "bomb_range", "bombs", "opps", "opp_cells", "cursed_opps",
        "items", "flames", "danger", "max_end", "bomb_block", "horizon",
        "shrink_margin", "next_shrink", "shrink_active", "cursed",
        "final_cells", "final_step", "endgame", "threats", "_threat_base",
        "_cached_targets", "_dist_cache", "_regions", "_avoid",
    )


class Agent:
    """Agente com fuga garantida por simulação e objetivos ponderados."""

    def __init__(self, player_id: int = 0, seed: int = 0) -> None:
        self.player_id = player_id
        self.seed = seed
        self.rng = random.Random(seed * 31 + 7919 * (player_id + 1))
        self.last_pos: tuple[int, int] | None = None
        self.last_delay = 2
        self.next_move_tick = 0
        self.prev_bombs: set[tuple[int, int]] = set()
        self.opp_range: dict[int, int] = {}
        self.prev_flames: set[tuple[int, int]] = set()
        self.fuse = 24
        self.flame_len = 4
        self.shrink_interval = 48
        self.prev_ttn: int | None = None
        self.curse_map: dict[str, str] = {}
        self.was_cursed = False
        self._deadline = float("inf")

    def reset(self, player_id: int, seed: int) -> None:
        self.__init__(player_id, seed)

    # ------------------------------------------------------------------ #
    # Decisão
    # ------------------------------------------------------------------ #
    def decide(self, observation: dict) -> str:
        me = observation["self"]
        if not me["alive"]:
            return "WAIT"
        self._deadline = time.perf_counter() + TIME_BUDGET
        self._observe(observation)
        view = self._build_view(observation)
        scores = {}
        for action in ACTIONS:
            if time.perf_counter() > self._deadline:
                scores[action] = -1500.0  # sem tempo para avaliar com segurança
            else:
                scores[action] = self._score_effective(action, view)

        best_action, best_key = "WAIT", None
        for intended in ACTIONS:
            outcomes = self._possible_outcomes(intended, view.cursed)
            values = [scores[effective] for effective in outcomes]
            # Sob maldição, primeiro garante o pior caso; depois a média.
            key = (min(values), sum(values) / len(values), self.rng.random())
            if best_key is None or key > best_key:
                best_action, best_key = intended, key
        return best_action

    def _possible_outcomes(self, intended: str, cursed: bool) -> list[str]:
        if not cursed:
            return [intended]
        if intended in self.curse_map:
            return [self.curse_map[intended]]
        seen = set(self.curse_map.values())
        # A permutação não tem pontos fixos: o comando nunca executa a si mesmo.
        options = [a for a in ACTIONS if a not in seen and a != intended]
        return options or [a for a in ACTIONS if a != intended]

    def _score_effective(self, action: str, view: View) -> float:
        """Nota de uma ação efetiva: segurança domina, utilidade desempata."""
        outcomes, danger, max_end, bomb_block, intended_pos = self._apply_first_step(
            action, view
        )
        # Oponentes podem disputar uma célula indefinidamente, então também se
        # verifica uma fuga que não passa por eles nem ao lado deles.
        avoid = self._opponent_zone(view)
        # Quando o resultado é incerto (disputa de célula), vale o pior caso.
        goals, first_safe, robust = INF, 0, INF
        threatened = False
        for pos1, nm1 in outcomes:
            if self._lethal(danger, pos1, 1):
                return -2000.0
            found, first, survive = self._escape(
                pos1, 1, nm1, view, danger, max_end, bomb_block
            )
            if found == 0:
                # Sem rota garantida: sobreviver mais vem primeiro, e a utilidade
                # desempata (por exemplo, atacar quem ocupa a célula final).
                hope = self._utility(action, intended_pos, view)
                if action == "BOMB" and view.can_bomb:
                    hope += self._bomb_value(view.pos, view)
                return -1000.0 + survive + 0.02 * hope
            goals, first_safe = min(goals, found), max(first_safe, first)
            robust_found, _, _ = self._escape(
                pos1, 1, nm1, view, danger, max_end, bomb_block, avoid
            )
            robust = min(robust, robust_found)
            if view.threats and not threatened:
                t_danger, t_max_end, t_block = self._threat_timeline(action, view)
                if not self._lethal(t_danger, pos1, 1):
                    t_found, _, _ = self._escape(
                        pos1, 1, nm1, view, t_danger, t_max_end, t_block
                    )
                    threatened = t_found == 0

        utility = self._utility(action, intended_pos, view)
        caution = self._caution(view)
        if action == "BOMB" and view.can_bomb:
            value = self._bomb_value(view.pos, view)
            if self._spoils_final(view):
                return -100.0 + value
            if goals < 2 or robust == 0:
                return -100.0 + value  # fuga frágil: só sob maldição, por acaso
            # Já estando numa zona de perigo, só vale bombardear para encurralar.
            if view.max_end.get(view.pos, -1) >= 1 and value < 50.0:
                return -100.0 + value
            # Bomba segura, mas inútil, é apenas desperdício.
            utility += value if value >= 5.0 else value - 30.0
        else:
            if action == "BOMB":
                utility -= 0.3  # sem bomba disponível, equivale a esperar
            if robust == 0:
                utility -= 25.0 * caution
        if threatened:
            utility -= THREAT_PENALTY * caution
        # Permanecer numa zona que vai explodir é arriscado (oponentes podem
        # fechar a saída): a penalidade cresce com a distância até a segurança.
        # A bomba recém-colocada é isenta, pois a fuga começa no tick seguinte.
        if (action != "BOMB" or not view.can_bomb) and first_safe > 1:
            utility -= 20.0 + 6.0 * (first_safe - 1)
        return utility + 0.5 * goals

    @staticmethod
    def _caution(view: View) -> float:
        """Peso das penalidades de cautela: dentro de uma zona de perigo, fugir
        vem antes de escolher a posição ideal."""
        return 0.3 if view.max_end.get(view.pos, -1) >= 1 else 1.0

    def _threat_timeline(self, action: str, view: View):
        """Linha do tempo do perigo supondo bombas novas dos oponentes próximos."""
        own = action == "BOMB" and view.can_bomb
        if not own:
            cached = getattr(view, "_threat_base", None)
            if cached is not None:
                return cached
        bombs = view.bombs + view.threats
        if own:
            bombs = bombs + [(view.pos[0], view.pos[1], view.bomb_range, 1 + self.fuse)]
        danger, bomb_block = self._timeline(view, bombs)
        result = (danger, self._max_end(danger), bomb_block)
        if not own:
            view._threat_base = result  # type: ignore[attr-defined]
        return result

    def _opponent_zone(self, view: View) -> set[tuple[int, int]]:
        cached = getattr(view, "_avoid", None)
        if cached is None:
            # Células que um oponente alcança em até OPP_REACH passos.
            cached = set(view.opp_cells)
            frontier = list(view.opp_cells)
            for _ in range(OPP_REACH):
                nxt = []
                for x, y in frontier:
                    for dx, dy in MOVES.values():
                        cell = (x + dx, y + dy)
                        if cell in cached or not self._passable(cell, view):
                            continue
                        cached.add(cell)
                        nxt.append(cell)
                frontier = nxt
            cached.discard(view.pos)
            view._avoid = cached  # type: ignore[attr-defined]
        return cached

    # ------------------------------------------------------------------ #
    # Memória entre ticks
    # ------------------------------------------------------------------ #
    def _observe(self, obs: dict) -> None:
        me = obs["self"]
        tick = obs["tick"]
        pos = (me["x"], me["y"])
        if self.last_pos is not None and pos != self.last_pos:
            # O motor usa o atraso vigente no momento do movimento.
            self.next_move_tick = tick + self.last_delay
        self.last_pos = pos
        self.last_delay = int(me["move_delay"])

        bombs_now = set()
        for bomb in obs["bombs"]:
            cell = (bomb["x"], bomb["y"])
            bombs_now.add(cell)
            if cell not in self.prev_bombs and tick > 0:
                self.fuse = int(bomb["timer"])
            owner = bomb["owner_id"]
            if owner != me["id"]:
                self.opp_range[owner] = max(self.opp_range.get(owner, 2), int(bomb["range"]))
        self.prev_bombs = bombs_now

        flames_now = set()
        for flame in obs["flames"]:
            cell = (flame["x"], flame["y"])
            flames_now.add(cell)
            if cell not in self.prev_flames:
                self.flame_len = max(self.flame_len, int(flame["expires_in"]))
        self.prev_flames = flames_now

        shrink = obs.get("shrink", {})
        ttn = shrink.get("ticks_to_next")
        if self.prev_ttn == 0 and shrink.get("active") and ttn:
            self.shrink_interval = int(ttn) + 1
        self.prev_ttn = ttn

        applied = any(
            event.get("type") == "curse_applied" and event.get("player") == me["id"]
            for event in obs.get("events", ())
        )
        if not me["cursed"] or applied:
            self.curse_map = {}
        elif self.was_cursed:
            self.curse_map[me["last_intended_action"]] = me["last_effective_action"]
        self.was_cursed = bool(me["cursed"])

    # ------------------------------------------------------------------ #
    # Percepção e linha do tempo do perigo
    # ------------------------------------------------------------------ #
    def _build_view(self, obs: dict) -> View:
        me = obs["self"]
        view = View()
        view.tick = obs["tick"]
        view.board = obs["board"]
        view.height = len(view.board)
        view.width = len(view.board[0])
        view.pos = (me["x"], me["y"])
        view.me = me
        view.delay = int(me["move_delay"])
        view.nm = self.next_move_tick - view.tick
        view.bomb_range = int(me["bomb_range"])
        view.cursed = bool(me["cursed"])

        view.bombs = [
            (b["x"], b["y"], int(b["range"]), max(1, int(b["timer"])))
            for b in obs["bombs"]
        ]
        bomb_cells = {(b[0], b[1]) for b in view.bombs}
        view.can_bomb = me["active_bombs"] < me["max_bombs"] and view.pos not in bomb_cells

        others = [p for p in obs["players"] if p["id"] != me["id"] and p["alive"]]
        view.opps = [(p["x"], p["y"]) for p in others]
        view.opp_cells = set(view.opps)
        view.cursed_opps = [(p["x"], p["y"]) for p in others if p["cursed"]]
        # Ameaças: bombas que oponentes próximos poderiam colocar agora.
        view.threats = []
        for p in others:
            blast_range = self.opp_range.get(p["id"], 2)
            if abs(p["x"] - me["x"]) + abs(p["y"] - me["y"]) <= blast_range + 4:
                view.threats.append((p["x"], p["y"], blast_range, 1 + self.fuse))
        view.items = {(i["x"], i["y"]): i["type"] for i in obs["items"]}
        view.flames = {(f["x"], f["y"]): int(f["expires_in"]) for f in obs["flames"]}

        shrink = obs.get("shrink", {})
        view.shrink_margin = int(shrink.get("margin", 0))
        view.shrink_active = bool(shrink.get("active"))
        ttn = shrink.get("ticks_to_next")
        view.next_shrink = None
        if ttn is not None and view.shrink_margin + 1 < min(view.width, view.height) // 2:
            view.next_shrink = int(ttn) if ttn > 0 else self.shrink_interval

        # Fim de jogo: só as células mais fundas sobrevivem ao último anel, e
        # quem estiver nelas quando ele fechar vence.
        final_margin = min(view.width, view.height) // 2 - 1
        view.final_cells = {
            (x, y)
            for y in range(view.height)
            for x in range(view.width)
            if view.board[y][x] in (".", "+") and self._depth(view, (x, y)) > final_margin
        }
        view.final_step = None
        if view.next_shrink is not None:
            remaining = final_margin - (view.shrink_margin + 1)
            view.final_step = view.next_shrink + remaining * self.shrink_interval
        view.endgame = (
            view.shrink_active and view.final_step is not None and view.final_step <= 120
        )

        danger, bomb_block = self._timeline(view, view.bombs)
        view.danger = danger
        view.bomb_block = bomb_block
        view.max_end = self._max_end(danger)
        view.horizon = self._horizon(view.max_end)
        return view

    def _blast(self, board, origin, blast_range) -> list[tuple[int, int]]:
        cells = [origin]
        ox, oy = origin
        height, width = len(board), len(board[0])
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for distance in range(1, blast_range + 1):
                x, y = ox + dx * distance, oy + dy * distance
                if not (0 <= x < width and 0 <= y < height):
                    break
                cell = board[y][x]
                if cell in ("#", "X"):
                    break
                cells.append((x, y))
                if cell == "+":
                    break
        return cells

    def _timeline(self, view: View, bombs: list[tuple[int, int, int, int]]):
        """Intervalos letais por célula, com reações em cadeia e fechamento."""
        work = [row[:] for row in view.board]
        steps = [b[3] for b in bombs]
        index = {(b[0], b[1]): i for i, b in enumerate(bombs)}
        heap = [(steps[i], i) for i in range(len(bombs))]
        heapq.heapify(heap)
        done = [False] * len(bombs)
        danger: dict[tuple[int, int], list[tuple[int, int]]] = {}
        length = self.flame_len

        while heap:
            step, i = heapq.heappop(heap)
            if done[i] or step != steps[i]:
                continue
            done[i] = True
            x, y, blast_range, _ = bombs[i]
            cells = self._blast(work, (x, y), blast_range)
            for cell in cells:
                danger.setdefault(cell, []).append((step, step + length - 1))
                j = index.get(cell)
                if j is not None and not done[j] and steps[j] > step:
                    steps[j] = step
                    heapq.heappush(heap, (step, j))
            # Caixas destruídas ampliam o alcance de explosões posteriores.
            for cx, cy in cells:
                if work[cy][cx] == "+":
                    work[cy][cx] = "."

        for cell, expires_in in view.flames.items():
            if expires_in >= 2:
                danger.setdefault(cell, []).append((1, expires_in - 1))

        # Anéis do fechamento: quem estiver no anel ao fim do tick anterior morre.
        if view.next_shrink is not None:
            limit = min(view.width, view.height) // 2
            ring_step, margin = view.next_shrink, view.shrink_margin + 1
            while ring_step <= RING_WINDOW and margin < limit:
                for cell in self._ring(view, margin):
                    danger.setdefault(cell, []).append((ring_step - 1, INF))
                ring_step += self.shrink_interval
                margin += 1

        bomb_block = {(b[0], b[1]): steps[i] for i, b in enumerate(bombs)}
        return danger, bomb_block

    def _ring(self, view: View, margin: int) -> list[tuple[int, int]]:
        left, right = margin, view.width - 1 - margin
        top, bottom = margin, view.height - 1 - margin
        cells = []
        for x in range(left, right + 1):
            cells.append((x, top))
            cells.append((x, bottom))
        for y in range(top + 1, bottom):
            cells.append((left, y))
            cells.append((right, y))
        return cells

    @staticmethod
    def _max_end(danger) -> dict[tuple[int, int], int]:
        return {cell: max(end for _, end in spans) for cell, spans in danger.items()}

    @staticmethod
    def _horizon(max_end) -> int:
        finite = [end for end in max_end.values() if end < INF]
        # Folga para desviar de uma explosão e voltar à célula depois dela.
        return min(HORIZON_CAP, (max(finite) if finite else 0) + 12)

    @staticmethod
    def _lethal(danger, cell, step) -> bool:
        for start, end in danger.get(cell, ()):
            if start <= step <= end:
                return True
        return False

    def _depth(self, view: View, cell) -> int:
        x, y = cell
        return min(x, y, view.width - 1 - x, view.height - 1 - y)

    # ------------------------------------------------------------------ #
    # Simulação de segurança
    # ------------------------------------------------------------------ #
    def _enterable(self, cell, step, view: View, danger, bomb_block, avoid=None) -> bool:
        x, y = cell
        if not (0 <= x < view.width and 0 <= y < view.height):
            return False
        if view.board[y][x] != ".":
            return False
        explode = bomb_block.get(cell)
        if explode is not None and step <= explode:
            return False
        # Oponentes bloqueiam a passagem nos primeiros ticks.
        if step <= 2 and cell in view.opp_cells:
            return False
        if avoid and cell in avoid:
            return False
        return not self._lethal(danger, cell, step)

    def _engine_walkable(self, cell, view: View) -> bool:
        """Regra de passagem do motor no próximo tick (ignora perigo futuro)."""
        x, y = cell
        if not (0 <= x < view.width and 0 <= y < view.height):
            return False
        if view.board[y][x] != "." or cell in view.bomb_block:
            return False
        # Chamas com expires_in <= 1 são removidas antes do movimento.
        return view.flames.get(cell, 0) < 2

    def _apply_first_step(self, action: str, view: View):
        """Resultados possíveis do próximo tick para uma ação efetiva.

        Reproduz a regra de movimento do motor: o passo acontece mesmo que a
        célula de destino vá explodir, e a segurança é avaliada depois.
        """
        danger, max_end, bomb_block = view.danger, view.max_end, view.bomb_block
        pos = view.pos
        nm = view.nm
        intended_pos = pos
        outcomes = [(pos, nm)]

        if action == "BOMB" and view.can_bomb:
            bombs = view.bombs + [(pos[0], pos[1], view.bomb_range, 1 + self.fuse)]
            danger, bomb_block = self._timeline(view, bombs)
            max_end = self._max_end(danger)
            # O dono pode permanecer e sair, mas não voltar: a célula atual não
            # é reavaliada como entrada enquanto ele não sai.
        elif action in MOVES:
            dx, dy = MOVES[action]
            target = (pos[0] + dx, pos[1] + dy)
            if self._engine_walkable(target, view):
                intended_pos = target
                if 1 >= nm:
                    moved = (target, 1 + view.delay)
                    contested = any(
                        abs(ox - target[0]) + abs(oy - target[1]) <= 1
                        for ox, oy in view.opps
                    )
                    if target in view.opp_cells or contested:
                        outcomes = [moved, (pos, nm)]
                    else:
                        outcomes = [moved]
        return outcomes, danger, max_end, bomb_block, intended_pos

    def _escape(self, pos, step, nm, view: View, danger, max_end, bomb_block, avoid=None):
        """Células seguras alcançáveis, tick da primeira delas e maior tick vivo."""
        horizon = max(self._horizon(max_end), step + 1)
        start = (pos, step, max(0, nm - step))
        queue = deque([(pos, step, nm)])
        seen = {start}
        goals: set[tuple[int, int]] = set()
        survive = step
        first_safe = INF
        nodes = 0

        while queue and nodes < ESCAPE_NODE_BUDGET:
            cell, s, move_at = queue.popleft()
            nodes += 1
            if nodes % 256 == 0 and time.perf_counter() > self._deadline:
                break
            survive = max(survive, s)
            if max_end.get(cell, -1) <= s:
                first_safe = min(first_safe, s)
                goals.add(cell)
                if len(goals) >= ESCAPE_GOALS:
                    break
                # Continua expandindo: células seguras atrás desta também contam.
            if s >= horizon:
                continue
            ns = s + 1
            if not self._lethal(danger, cell, ns):
                key = (cell, ns, max(0, move_at - ns))
                if key not in seen:
                    seen.add(key)
                    queue.append((cell, ns, move_at))
            if ns >= move_at:
                for dx, dy in MOVES.values():
                    target = (cell[0] + dx, cell[1] + dy)
                    if not self._enterable(target, ns, view, danger, bomb_block, avoid):
                        continue
                    new_move_at = ns + view.delay
                    key = (target, ns, max(0, new_move_at - ns))
                    if key not in seen:
                        seen.add(key)
                        queue.append((target, ns, new_move_at))
        return len(goals), first_safe, survive

    # ------------------------------------------------------------------ #
    # Utilidade dos objetivos
    # ------------------------------------------------------------------ #
    def _passable(self, cell, view: View) -> bool:
        x, y = cell
        if not (0 <= x < view.width and 0 <= y < view.height):
            return False
        if view.board[y][x] != "." or cell in view.bomb_block:
            return False
        if cell in view.flames or view.items.get(cell) == "CURSE":
            return False
        return True

    def _distances(self, origin, view: View, limit: int = 30) -> dict:
        dist = {origin: 0}
        queue = deque([origin])
        while queue:
            cell = queue.popleft()
            d = dist[cell]
            if d >= limit:
                continue
            for dx, dy in MOVES.values():
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt not in dist and self._passable(nxt, view):
                    dist[nxt] = d + 1
                    queue.append(nxt)
        return dist

    def _targets(self, view: View) -> list[tuple[tuple[int, int], float]]:
        """Objetivos com valor; calculados uma vez por tick."""
        cached = getattr(view, "_cached_targets", None)
        if cached is not None:
            return cached
        me = view.me
        targets: list[tuple[tuple[int, int], float]] = []

        for cell, kind in view.items.items():
            if cell in view.max_end:
                continue  # será destruído por uma explosão
            if kind == "SPEED_UP":
                value = 40.0 if view.delay > 1 else 6.0
            elif kind == "BOMB_UP":
                value = 32.0 if me["max_bombs"] < 4 else 10.0
            elif kind == "RANGE_UP":
                value = 28.0 if me["bomb_range"] < 5 else 6.0
            elif kind == "SHIELD":
                value = 30.0
            else:
                continue
            targets.append((cell, value))

        # Pontos de bomba: caixas e oponentes atingíveis com rota de fuga.
        if me["max_bombs"] > 0:
            reach = self._distances(view.pos, view, limit=14)
            spots = []
            for cell, d in reach.items():
                if cell in view.max_end:
                    continue
                value = self._bomb_value(cell, view)
                if value >= 5.0:
                    spots.append((value * DECAY**d, value, cell))
            spots.sort(reverse=True)
            for _, value, cell in spots[:6]:
                if self._static_escape(cell, view):
                    targets.append((cell, value))

        if view.endgame:
            for cell in view.final_cells:
                targets.append((cell, 150.0))

        # Fechamento da arena: entrar na região que continuará aberta.
        if view.next_shrink is not None:
            urgent = view.shrink_active or view.next_shrink <= 160
            if urgent:
                safe_depth = view.shrink_margin + 2
                value = 60.0 if view.next_shrink <= 60 else 30.0
                for (x, y), size in self._safe_regions(view).items():
                    if size >= self._needed_region(view):
                        # Quanto mais fundo, mais fechamentos a célula aguenta.
                        depth = self._depth(view, (x, y))
                        targets.append(((x, y), value + 8.0 * (depth - safe_depth)))

        # Amaldiçoado: encostar em um oponente transmite o debuff.
        if view.cursed:
            for ox, oy in view.opps:
                if (ox, oy) in view.cursed_opps:
                    continue
                for dx, dy in MOVES.values():
                    targets.append(((ox + dx, oy + dy), 35.0))

        # Sem objetivos melhores, ocupa o centro e pressiona oponentes.
        cx, cy = view.width // 2, view.height // 2
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                targets.append(((cx + dx, cy + dy), 4.0))
        for ox, oy in view.opps:
            for dx, dy in MOVES.values():
                targets.append(((ox + 2 * dx, oy + 2 * dy), 6.0))

        view._cached_targets = targets  # type: ignore[attr-defined]
        return targets

    def _utility(self, action: str, intended_pos, view: View) -> float:
        cache = getattr(view, "_dist_cache", None)
        if cache is None:
            cache = {}
            view._dist_cache = cache  # type: ignore[attr-defined]
        if intended_pos not in cache:
            cache[intended_pos] = self._distances(intended_pos, view)
        dist = cache[intended_pos]

        best = 0.0
        for cell, value in self._targets(view):
            d = dist.get(cell)
            if d is not None:
                best = max(best, value * DECAY**d)

        local = 0.0
        free = sum(
            1
            for dx, dy in MOVES.values()
            if self._passable((intended_pos[0] + dx, intended_pos[1] + dy), view)
        )
        local += 0.4 * free
        if free <= 1:
            # Ponta de beco: um oponente por perto pode fechar a única saída.
            near = min((dist.get(opp, INF) for opp in view.opps), default=INF)
            if near <= DEAD_END_RADIUS:
                local -= DEAD_END_PENALTY * self._caution(view)
        if not view.cursed:
            for ox, oy in view.cursed_opps:
                if abs(ox - intended_pos[0]) + abs(oy - intended_pos[1]) <= 1:
                    local -= 15.0
        if view.endgame and intended_pos in view.final_cells:
            local += 40.0  # segurar a célula final
        if view.items.get(intended_pos) == "CURSE":
            local -= 40.0
        if action == "WAIT":
            local -= 0.2
        if view.next_shrink is not None and (view.shrink_active or view.next_shrink <= 80):
            # Evita bolsões que ficam emparedados quando o próximo anel fecha.
            size = self._safe_regions(view).get(intended_pos)
            if size is not None and size < self._needed_region(view):
                local -= 50.0
        return best + local

    def _safe_regions(self, view: View) -> dict[tuple[int, int], int]:
        """Tamanho do componente livre de cada célula que sobrevive ao próximo anel."""
        cached = getattr(view, "_regions", None)
        if cached is not None:
            return cached
        min_depth = view.shrink_margin + 2
        sizes: dict[tuple[int, int], int] = {}
        for y in range(view.height):
            for x in range(view.width):
                start = (x, y)
                if start in sizes or view.board[y][x] != "." or self._depth(view, start) < min_depth:
                    continue
                component = [start]
                seen = {start}
                queue = deque([start])
                while queue:
                    cell = queue.popleft()
                    for dx, dy in MOVES.values():
                        nxt = (cell[0] + dx, cell[1] + dy)
                        if nxt in seen or self._depth(view, nxt) < min_depth:
                            continue
                        if view.board[nxt[1]][nxt[0]] != ".":
                            continue
                        seen.add(nxt)
                        component.append(nxt)
                        queue.append(nxt)
                for cell in component:
                    sizes[cell] = len(component)
        view._regions = sizes  # type: ignore[attr-defined]
        return sizes

    def _needed_region(self, view: View) -> int:
        regions = self._safe_regions(view)
        return min(6, max(regions.values(), default=0))

    def _spoils_final(self, view: View) -> bool:
        """A bomba deixaria a célula final em chamas na hora do último anel?"""
        if view.final_step is None:
            return False
        blast = self._blast(view.board, view.pos, view.bomb_range)
        if not any(cell in view.final_cells for cell in blast):
            return False
        flames_end = self.fuse + self.flame_len
        return flames_end >= view.final_step - 2

    def _bomb_value(self, cell, view: View) -> float:
        cells = self._blast(view.board, cell, view.bomb_range)
        value = 0.0
        # Expulsar quem ocupa a célula final, a tempo de tomá-la depois.
        if view.endgame and view.final_step - (self.fuse + self.flame_len) >= 3:
            for opp in view.opps:
                if opp in view.final_cells and opp in cells:
                    value += 60.0
        for x, y in cells:
            if view.board[y][x] == "+" and (x, y) not in view.max_end:
                value += 6.0
            kind = view.items.get((x, y))
            if kind and kind != "CURSE":
                value -= 8.0
        blast = set(cells)
        for opp in view.opps:
            if opp in blast:
                value += 10.0
                room = self._opponent_room(opp, blast, view)
                if room == 0:
                    value += 80.0
                elif room <= 2:
                    value += 20.0
        return value

    def _opponent_room(self, opp, blast, view: View, depth: int = 6) -> int:
        """Quantas células fora do alcance o oponente consegue alcançar."""
        seen = {opp}
        queue = deque([(opp, 0)])
        room = 0
        while queue:
            cell, d = queue.popleft()
            if cell not in blast and cell not in view.max_end:
                room += 1
                if room > 2:
                    return room
            if d >= depth:
                continue
            for dx, dy in MOVES.values():
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt in seen or nxt == view.pos:
                    continue
                x, y = nxt
                if view.board[y][x] != "." or nxt in view.bomb_block:
                    continue
                seen.add(nxt)
                queue.append((nxt, d + 1))
        return room

    def _static_escape(self, origin, view: View, depth: int = 6) -> bool:
        blast = set(self._blast(view.board, origin, view.bomb_range))
        seen = {origin}
        queue = deque([(origin, 0)])
        while queue:
            cell, d = queue.popleft()
            if cell not in blast and cell not in view.max_end:
                return True
            if d >= depth:
                continue
            for dx, dy in MOVES.values():
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt not in seen and self._passable(nxt, view):
                    seen.add(nxt)
                    queue.append((nxt, d + 1))
        return False
