from __future__ import annotations

import random
from collections import deque
from typing import Iterable

from .arena import generate_arena
from .config import GameConfig
from .enums import Action, ItemType, MOVE_DELTAS, Tile
from .state import Bomb, Flame, GameResult, Item, Player


class GameEngine:
    def __init__(self, agent_names: list[str], seed: int = 42, config: GameConfig | None = None):
        self.config = config or GameConfig()
        self.config.validate()
        if not 2 <= len(agent_names) <= 4:
            raise ValueError("Informe de 2 a 4 agentes.")

        self.seed = seed
        self.rng = random.Random(seed)
        arena = generate_arena(
            width=self.config.width,
            height=self.config.height,
            player_count=len(agent_names),
            crate_density=self.config.crate_density,
            item_probability=self.config.item_probability,
            seed=seed,
        )
        self.grid = arena.grid
        self.hidden_items = arena.hidden_items
        self.players: dict[int, Player] = {}
        for player_id, (name, (x, y)) in enumerate(zip(agent_names, arena.spawns)):
            self.players[player_id] = Player(
                player_id=player_id,
                name=name,
                x=x,
                y=y,
                max_bombs=self.config.initial_max_bombs,
                bomb_range=self.config.initial_bomb_range,
                move_delay=self.config.initial_move_delay,
            )

        self.bombs: dict[int, Bomb] = {}
        self.items: dict[tuple[int, int], Item] = {}
        self.flames: dict[tuple[int, int], Flame] = {}
        self.tick = 0
        self.shrink_margin = 0
        self.next_bomb_id = 1
        self.game_over = False
        self.result: GameResult | None = None
        self.events: list[dict] = []
        self.event_history: list[dict] = []
        self.next_event_id = 1

    @property
    def width(self) -> int:
        return self.config.width

    @property
    def height(self) -> int:
        return self.config.height

    def alive_players(self) -> list[Player]:
        return [p for p in self.players.values() if p.alive]

    def bomb_at(self, pos: tuple[int, int]) -> Bomb | None:
        for bomb in self.bombs.values():
            if bomb.pos == pos:
                return bomb
        return None

    def _make_curse_mapping(self) -> dict[Action, Action]:
        actions = list(Action)
        shuffled = actions[:]
        # Produz uma permutação sem pontos fixos: nenhum comando executa a si mesmo.
        for _ in range(100):
            self.rng.shuffle(shuffled)
            if all(a != b for a, b in zip(actions, shuffled)):
                return dict(zip(actions, shuffled))
        # Fallback determinístico por rotação.
        shifted = actions[1:] + actions[:1]
        return dict(zip(actions, shifted))

    def _apply_curse(self, player: Player, mapping: dict[Action, Action] | None = None) -> None:
        player.curse_mapping = dict(mapping) if mapping else self._make_curse_mapping()
        player.curse_acquired_tick = self.tick
        self.events.append({"type": "curse_applied", "player": player.player_id})

    def _effective_action(self, player: Player, intended: Action) -> Action:
        if player.curse_mapping:
            return player.curse_mapping[intended]
        return intended

    def _tile_blocks(self, pos: tuple[int, int]) -> bool:
        x, y = pos
        if not (0 <= x < self.width and 0 <= y < self.height):
            return True
        return self.grid[y][x] in (Tile.WALL, Tile.CRATE, Tile.SHRINK_WALL)

    def is_walkable(self, pos: tuple[int, int], player_id: int) -> bool:
        if self._tile_blocks(pos):
            return False
        bomb = self.bomb_at(pos)
        if bomb is not None and player_id not in bomb.passable_by:
            return False
        # Chamas persistentes continuam visíveis, mas são tratadas como células
        # bloqueadas. Isso evita a eliminação aparentemente "fora da explosão"
        # causada por um agente entrar em uma chama no tick seguinte.
        if self.config.active_flames_block_movement and pos in self.flames:
            return False
        return True

    def _parse_action(self, value: str | Action | None) -> Action:
        if isinstance(value, Action):
            return value
        try:
            return Action(str(value).upper())
        except (ValueError, AttributeError):
            return Action.WAIT

    def step(self, intended_actions: dict[int, str | Action]) -> None:
        if self.game_over:
            return

        self.events = []
        self.tick += 1
        self._expire_flames()
        self._apply_shrink_if_due()

        effective: dict[int, Action] = {}
        for player in self.alive_players():
            intended = self._parse_action(intended_actions.get(player.player_id, Action.WAIT))
            player.last_intended_action = intended
            actual = self._effective_action(player, intended)
            player.last_effective_action = actual
            effective[player.player_id] = actual

        self._resolve_movements(effective)
        self._update_bomb_passability()
        self._resolve_bomb_placements(effective)
        self._collect_items()
        self._transmit_curses()
        self._explode_due_bombs()
        self._damage_players_on_flames()
        self._finish_if_needed()
        self._finalize_step_events()


    def _finalize_step_events(self) -> None:
        """Adiciona metadados estáveis e preserva um log auditável da partida."""
        for event in self.events:
            event.setdefault("tick", self.tick)
            event.setdefault("event_id", self.next_event_id)
            self.next_event_id += 1
            self.event_history.append(dict(event))

    def _resolve_movements(self, actions: dict[int, Action]) -> None:
        proposals: dict[int, tuple[int, int]] = {}
        current_positions = {p.player_id: p.pos for p in self.alive_players()}
        occupants = {p.pos: p.player_id for p in self.alive_players()}

        for player in self.alive_players():
            action = actions[player.player_id]
            if action not in MOVE_DELTAS or self.tick < player.next_move_tick:
                proposals[player.player_id] = player.pos
                continue
            dx, dy = MOVE_DELTAS[action]
            target = (player.x + dx, player.y + dy)
            if self.is_walkable(target, player.player_id):
                proposals[player.player_id] = target
            else:
                proposals[player.player_id] = player.pos

        # Duas pessoas não podem ocupar a mesma célula.
        target_groups: dict[tuple[int, int], list[int]] = {}
        for pid, target in proposals.items():
            target_groups.setdefault(target, []).append(pid)
        for target, pids in target_groups.items():
            if len(pids) > 1:
                for pid in pids:
                    proposals[pid] = current_positions[pid]

        # Impede troca direta A<->B e entrada na célula de alguém que não saiu.
        for pid, target in list(proposals.items()):
            if target == current_positions[pid]:
                continue
            other_id = occupants.get(target)
            if other_id is None:
                continue
            other_target = proposals.get(other_id, current_positions[other_id])
            if other_target == current_positions[pid] or other_target == target:
                proposals[pid] = current_positions[pid]

        for player in self.alive_players():
            old = player.pos
            new = proposals[player.player_id]
            if new != old:
                player.pos = new
                player.next_move_tick = self.tick + player.move_delay
                self.events.append(
                    {"type": "move", "player": player.player_id, "from": old, "to": new}
                )

    def _resolve_bomb_placements(self, actions: dict[int, Action]) -> None:
        for player in self.alive_players():
            if actions[player.player_id] != Action.BOMB:
                continue
            if player.active_bombs >= player.max_bombs or self.bomb_at(player.pos):
                continue
            bomb = Bomb(
                bomb_id=self.next_bomb_id,
                owner_id=player.player_id,
                x=player.x,
                y=player.y,
                explode_tick=self.tick + self.config.bomb_fuse_ticks,
                blast_range=player.bomb_range,
                passable_by={player.player_id},
            )
            self.next_bomb_id += 1
            self.bombs[bomb.bomb_id] = bomb
            player.active_bombs += 1
            self.events.append(
                {
                    "type": "bomb_placed",
                    "player": player.player_id,
                    "bomb_id": bomb.bomb_id,
                    "position": bomb.pos,
                    "explode_tick": bomb.explode_tick,
                }
            )

    def _update_bomb_passability(self) -> None:
        for bomb in self.bombs.values():
            for player_id in list(bomb.passable_by):
                player = self.players[player_id]
                if not player.alive or player.pos != bomb.pos:
                    bomb.passable_by.discard(player_id)

    def _collect_items(self) -> None:
        for player in self.alive_players():
            item = self.items.pop(player.pos, None)
            if item is None:
                continue
            player.items_collected += 1
            player.score += 5
            if item.item_type == ItemType.BOMB_UP:
                player.max_bombs += 1
            elif item.item_type == ItemType.RANGE_UP:
                player.bomb_range += 1
            elif item.item_type == ItemType.SPEED_UP:
                player.move_delay = max(self.config.minimum_move_delay, player.move_delay - 1)
            elif item.item_type == ItemType.SHIELD:
                player.shields += 1
            elif item.item_type == ItemType.CURSE:
                self._apply_curse(player)
            self.events.append(
                {
                    "type": "item_collected",
                    "player": player.player_id,
                    "item": item.item_type.value,
                }
            )

    def _transmit_curses(self) -> None:
        players = sorted(self.alive_players(), key=lambda p: p.player_id)
        transferred_sources: set[int] = set()
        for source in players:
            if (
                not source.cursed
                or source.player_id in transferred_sources
                or source.curse_acquired_tick == self.tick
            ):
                continue
            candidates = [
                target
                for target in players
                if target.player_id != source.player_id
                and not target.cursed
                and self.tick >= target.curse_immunity_until
                and abs(target.x - source.x) + abs(target.y - source.y) == 1
            ]
            if not candidates:
                continue
            target = candidates[0]
            mapping = source.curse_mapping
            source.curse_mapping = None
            source.curse_acquired_tick = -1
            source.curse_immunity_until = self.tick + self.config.curse_source_immunity_ticks
            self._apply_curse(target, mapping)
            transferred_sources.add(source.player_id)
            self.events.append(
                {
                    "type": "curse_transferred",
                    "from": source.player_id,
                    "to": target.player_id,
                }
            )

    def _expire_flames(self) -> None:
        for pos, flame in list(self.flames.items()):
            if flame.expires_tick <= self.tick:
                del self.flames[pos]

    def _blast_cells(self, bomb: Bomb) -> Iterable[tuple[int, int]]:
        yield bomb.pos
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for distance in range(1, bomb.blast_range + 1):
                pos = (bomb.x + dx * distance, bomb.y + dy * distance)
                x, y = pos
                tile = self.grid[y][x]
                if tile in (Tile.WALL, Tile.SHRINK_WALL):
                    break
                yield pos
                if tile == Tile.CRATE:
                    break

    def _explode_due_bombs(self) -> None:
        queue: deque[int] = deque(
            bomb_id for bomb_id, bomb in self.bombs.items() if bomb.explode_tick <= self.tick
        )
        exploded: set[int] = set()
        while queue:
            bomb_id = queue.popleft()
            if bomb_id in exploded or bomb_id not in self.bombs:
                continue
            bomb = self.bombs.pop(bomb_id)
            exploded.add(bomb_id)
            owner = self.players[bomb.owner_id]
            owner.active_bombs = max(0, owner.active_bombs - 1)
            blast_cells = list(self._blast_cells(bomb))
            self.events.append(
                {
                    "type": "bomb_exploded",
                    "player": bomb.owner_id,
                    "bomb_id": bomb.bomb_id,
                    "position": bomb.pos,
                    "cells": blast_cells,
                }
            )

            for pos in blast_cells:
                x, y = pos
                tile = self.grid[y][x]
                if tile == Tile.CRATE:
                    self.grid[y][x] = Tile.FLOOR
                    owner.score += 1
                    item_type = self.hidden_items.pop(pos, None)
                    if item_type is not None:
                        self.items[pos] = Item(item_type=item_type, x=x, y=y)
                    self.events.append({"type": "crate_destroyed", "position": pos})
                else:
                    # Uma chama posterior substitui a anterior apenas se durar mais.
                    current = self.flames.get(pos)
                    expires = self.tick + self.config.flame_duration_ticks
                    if current is None or current.expires_tick < expires:
                        self.flames[pos] = Flame(
                            x=x,
                            y=y,
                            expires_tick=expires,
                            owner_id=bomb.owner_id,
                            created_tick=self.tick,
                            bomb_id=bomb.bomb_id,
                            bomb_position=bomb.pos,
                        )

                # Itens expostos são destruídos por explosões posteriores.
                if pos in self.items and tile != Tile.CRATE:
                    del self.items[pos]

                chained = self.bomb_at(pos)
                if chained is not None and chained.bomb_id not in exploded:
                    queue.append(chained.bomb_id)

    def _damage_players_on_flames(self) -> None:
        for player in self.alive_players():
            flame = self.flames.get(player.pos)
            if flame is None:
                continue
            if player.shields > 0:
                player.shields -= 1
                self.events.append({"type": "shield_used", "player": player.player_id})
                continue
            reason = "bomb_blast" if flame.created_tick == self.tick else "lingering_flame"
            self._kill_player(
                player,
                killer_id=flame.owner_id,
                reason=reason,
                source={
                    "bomb_id": flame.bomb_id,
                    "bomb_position": flame.bomb_position,
                    "flame_created_tick": flame.created_tick,
                },
            )

    def _kill_player(
        self,
        player: Player,
        killer_id: int | None,
        reason: str,
        source: dict | None = None,
    ) -> None:
        if not player.alive:
            return
        player.alive = False
        player.curse_mapping = None
        if killer_id is not None and killer_id != player.player_id:
            killer = self.players[killer_id]
            killer.kills += 1
            killer.score += 100
        elif killer_id == player.player_id:
            player.score -= 10
        event = {
            "type": "player_eliminated",
            "player": player.player_id,
            "killer": killer_id,
            "reason": reason,
            "position": player.pos,
            "tick": self.tick,
        }
        if source:
            event.update({key: value for key, value in source.items() if value is not None})
        self.events.append(event)

    def _apply_shrink_if_due(self) -> None:
        if self.tick < self.config.shrink_start_tick:
            return
        elapsed = self.tick - self.config.shrink_start_tick
        if elapsed % self.config.shrink_interval_ticks != 0:
            return

        margin = self.shrink_margin + 1
        if margin >= min(self.width, self.height) // 2:
            return
        ring: set[tuple[int, int]] = set()
        left, right = margin, self.width - 1 - margin
        top, bottom = margin, self.height - 1 - margin
        for x in range(left, right + 1):
            ring.add((x, top))
            ring.add((x, bottom))
        for y in range(top, bottom + 1):
            ring.add((left, y))
            ring.add((right, y))

        for pos in ring:
            x, y = pos
            self.grid[y][x] = Tile.SHRINK_WALL
            self.hidden_items.pop(pos, None)
            self.items.pop(pos, None)
            self.flames.pop(pos, None)
            bomb = self.bomb_at(pos)
            if bomb is not None:
                owner = self.players[bomb.owner_id]
                owner.active_bombs = max(0, owner.active_bombs - 1)
                self.bombs.pop(bomb.bomb_id, None)
            for player in self.alive_players():
                if player.pos == pos:
                    self._kill_player(player, killer_id=None, reason="arena_shrink")

        self.shrink_margin = margin
        self.events.append({"type": "arena_shrunk", "margin": margin})

    def _finish_if_needed(self) -> None:
        alive = self.alive_players()
        reason = None
        winner_ids: list[int] = []
        if len(alive) <= 1:
            reason = "last_player_standing"
            winner_ids = [p.player_id for p in alive]
        elif self.tick >= self.config.max_ticks:
            reason = "maximum_time"
            best_score = max(p.score for p in alive)
            winner_ids = [p.player_id for p in alive if p.score == best_score]

        if reason is None:
            return
        self.game_over = True
        standings = sorted(
            [
                {
                    "player_id": p.player_id,
                    "name": p.name,
                    "alive": p.alive,
                    "score": p.score,
                    "kills": p.kills,
                    "items": p.items_collected,
                }
                for p in self.players.values()
            ],
            key=lambda row: (row["player_id"] not in winner_ids, -row["score"], -row["kills"]),
        )
        self.result = GameResult(
            winner_ids=winner_ids,
            reason=reason,
            ticks=self.tick,
            standings=standings,
        )

    def _ticks_to_next_shrink(self) -> int | None:
        if self.tick < self.config.shrink_start_tick:
            return self.config.shrink_start_tick - self.tick
        elapsed = self.tick - self.config.shrink_start_tick
        remainder = elapsed % self.config.shrink_interval_ticks
        return 0 if remainder == 0 else self.config.shrink_interval_ticks - remainder

    def observation_for(self, player_id: int) -> dict:
        player = self.players[player_id]
        symbols = {
            Tile.FLOOR: ".",
            Tile.WALL: "#",
            Tile.CRATE: "+",
            Tile.SHRINK_WALL: "X",
        }
        observation = {
            "tick": self.tick,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "board": [[symbols[cell] for cell in row] for row in self.grid],
            "self": {
                "id": player.player_id,
                "name": player.name,
                "x": player.x,
                "y": player.y,
                "alive": player.alive,
                "max_bombs": player.max_bombs,
                "active_bombs": player.active_bombs,
                "bomb_range": player.bomb_range,
                "move_delay": player.move_delay,
                "shields": player.shields,
                "cursed": player.cursed,
                "score": player.score,
                "last_intended_action": player.last_intended_action.value,
                "last_effective_action": player.last_effective_action.value,
            },
            "players": [
                {
                    "id": other.player_id,
                    "name": other.name,
                    "x": other.x,
                    "y": other.y,
                    "alive": other.alive,
                    "cursed": other.cursed,
                    "score": other.score,
                }
                for other in self.players.values()
            ],
            "bombs": [
                {
                    "x": bomb.x,
                    "y": bomb.y,
                    "owner_id": bomb.owner_id,
                    "timer": max(0, bomb.explode_tick - self.tick),
                    "range": bomb.blast_range,
                }
                for bomb in self.bombs.values()
            ],
            "flames": [
                {"x": flame.x, "y": flame.y, "expires_in": flame.expires_tick - self.tick}
                for flame in self.flames.values()
            ],
            "items": [
                {"x": item.x, "y": item.y, "type": item.item_type.value}
                for item in self.items.values()
            ],
            "shrink": {
                "active": self.tick >= self.config.shrink_start_tick,
                "margin": self.shrink_margin,
                "ticks_to_next": self._ticks_to_next_shrink(),
            },
            "available_actions": [action.value for action in Action],
            "events": list(self.events),
        }
        if self.config.reveal_curse_mapping and player.curse_mapping:
            observation["self"]["curse_mapping"] = {
                key.value: value.value for key, value in player.curse_mapping.items()
            }
        return observation
