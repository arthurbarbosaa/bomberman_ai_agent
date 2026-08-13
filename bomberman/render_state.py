from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PlayerVisual:
    player_id: int
    x: int
    y: int
    alive: bool
    cursed: bool
    shields: int
    last_effective_action: str

    @property
    def pos(self) -> tuple[int, int]:
        return self.x, self.y


@dataclass(frozen=True, slots=True)
class RenderSnapshot:
    """Cópia somente-leitura dos dados necessários para desenhar um frame.

    O motor continua inteiramente discreto. Esta estrutura existe apenas para
    o renderizador e impede que interpolação visual altere colisões ou dano.
    """

    tick: int
    grid: tuple[tuple[int, ...], ...]
    players: dict[int, PlayerVisual]
    bombs: tuple[dict[str, Any], ...]
    flames: tuple[dict[str, Any], ...]
    items: tuple[dict[str, Any], ...]


def capture_snapshot(engine) -> RenderSnapshot:
    return RenderSnapshot(
        tick=engine.tick,
        grid=tuple(tuple(int(cell) for cell in row) for row in engine.grid),
        players={
            player.player_id: PlayerVisual(
                player_id=player.player_id,
                x=player.x,
                y=player.y,
                alive=player.alive,
                cursed=player.cursed,
                shields=player.shields,
                last_effective_action=player.last_effective_action.value,
            )
            for player in engine.players.values()
        },
        bombs=tuple(
            {
                "bomb_id": bomb.bomb_id,
                "owner_id": bomb.owner_id,
                "x": bomb.x,
                "y": bomb.y,
                "explode_tick": bomb.explode_tick,
                "range": bomb.blast_range,
            }
            for bomb in engine.bombs.values()
        ),
        flames=tuple(
            {
                "x": flame.x,
                "y": flame.y,
                "expires_tick": flame.expires_tick,
                "created_tick": flame.created_tick,
                "owner_id": flame.owner_id,
                "bomb_id": flame.bomb_id,
                "bomb_position": flame.bomb_position,
            }
            for flame in engine.flames.values()
        ),
        items=tuple(
            {"x": item.x, "y": item.y, "type": item.item_type.value}
            for item in engine.items.values()
        ),
    )


@dataclass(frozen=True, slots=True)
class VisualTransition:
    before: RenderSnapshot
    after: RenderSnapshot
    events: tuple[dict[str, Any], ...]
    movement_phase_end: float = 0.55
    elimination_phase_start: float = 0.72

    def phase_snapshot(self, progress: float) -> RenderSnapshot:
        """Retorna o estado visual adequado à fase do tick.

        Antes do fim da fase de movimento, bombas/caixas/chamas permanecem no
        estado anterior. Depois disso, o estado lógico posterior é exibido.
        """
        return self.before if progress < self.movement_phase_end else self.after

    def player_position(self, player_id: int, progress: float) -> tuple[float, float]:
        before = self.before.players[player_id]
        after = self.after.players[player_id]
        if progress >= self.movement_phase_end:
            return float(after.x), float(after.y)
        local = max(0.0, min(1.0, progress / self.movement_phase_end))
        # Smoothstep: movimento contínuo, mas sem overshoot.
        eased = local * local * (3.0 - 2.0 * local)
        return (
            before.x + (after.x - before.x) * eased,
            before.y + (after.y - before.y) * eased,
        )

    def player_visible(self, player_id: int, progress: float) -> bool:
        before = self.before.players[player_id]
        after = self.after.players[player_id]
        if after.alive:
            return True
        # Quem morreu neste tick permanece visível até chegar à posição lógica
        # de eliminação; só então desaparece. Isso evita a "morte à distância".
        if before.alive and not after.alive:
            return progress < self.elimination_phase_start
        return False

    def elimination_for(self, player_id: int) -> dict[str, Any] | None:
        for event in self.events:
            if event.get("type") == "player_eliminated" and event.get("player") == player_id:
                return event
        return None
