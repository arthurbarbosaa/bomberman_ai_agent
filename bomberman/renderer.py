from __future__ import annotations

from pathlib import Path

from .enums import Action, ItemType, Tile
from .render_state import RenderSnapshot, VisualTransition, capture_snapshot


PLAYER_COLORS = [
    (65, 105, 225),
    (220, 20, 60),
    (46, 139, 87),
    (148, 0, 211),
]

DIRECTION_OFFSETS = {
    "up": 0,
    "right": 3,
    "down": 6,
    "left": 9,
}

FLAME_PART_OFFSETS = {
    "center": 0,
    "horizontal": 2,
    "vertical": 4,
    "end_up": 6,
    "end_right": 8,
    "end_down": 10,
    "end_left": 12,
}


class SpriteAtlas:
    """Carrega sprites avulsos e frames de spritesheets."""

    def __init__(self, pygame, cell_size: int) -> None:
        self.pygame = pygame
        self.cell_size = cell_size
        asset_root = Path(__file__).resolve().parents[1] / "assets"
        self.sprite_root = asset_root / "sprites"
        self.sheet_root = asset_root / "sheets"
        self.cache: dict[tuple[str, tuple[int, int]], object] = {}
        self.sheet_cache: dict[str, object] = {}
        self.frame_cache: dict[tuple[str, int, tuple[int, int]], object] = {}

    def get(self, name: str, size: tuple[int, int] | None = None):
        size = size or (self.cell_size, self.cell_size)
        key = (name, size)
        if key in self.cache:
            return self.cache[key]
        path = self.sprite_root / name
        if not path.exists():
            raise FileNotFoundError(f"Sprite ausente: {path}")
        image = self.pygame.image.load(str(path)).convert_alpha()
        if image.get_size() != size:
            image = self.pygame.transform.scale(image, size)
        self.cache[key] = image
        return image

    def get_sheet_frame(
        self,
        sheet_name: str,
        frame_index: int,
        size: tuple[int, int] | None = None,
        source_size: tuple[int, int] = (32, 32),
    ):
        size = size or (self.cell_size, self.cell_size)
        key = (sheet_name, frame_index, size)
        if key in self.frame_cache:
            return self.frame_cache[key]

        sheet = self.sheet_cache.get(sheet_name)
        if sheet is None:
            path = self.sheet_root / sheet_name
            if not path.exists():
                raise FileNotFoundError(f"Spritesheet ausente: {path}")
            sheet = self.pygame.image.load(str(path)).convert_alpha()
            self.sheet_cache[sheet_name] = sheet

        fw, fh = source_size
        frame_count = max(1, sheet.get_width() // fw)
        frame_index %= frame_count
        frame = self.pygame.Surface((fw, fh), self.pygame.SRCALPHA)
        frame.blit(sheet, (0, 0), self.pygame.Rect(frame_index * fw, 0, fw, fh))
        if frame.get_size() != size:
            frame = self.pygame.transform.scale(frame, size)
        self.frame_cache[key] = frame
        return frame


def run_visual(
    engine,
    controllers,
    cell_size: int = 42,
    render_fps: int = 60,
) -> None:
    """Executa o modo visual sem misturar coordenadas gráficas e lógicas.

    Cada tick do motor é resolvido integralmente. Depois, o renderizador anima a
    transição entre o snapshot anterior e o posterior. Assim, colisões, dano e
    vencedor nunca dependem da interpolação dos sprites.
    """
    try:
        import pygame
    except ImportError as exc:
        raise RuntimeError(
            "O modo visual requer pygame. Execute: python -m pip install -r requirements.txt"
        ) from exc

    pygame.init()
    panel_height = 136
    screen = pygame.display.set_mode(
        (engine.width * cell_size, engine.height * cell_size + panel_height)
    )
    pygame.display.set_caption("Bomberman AI Arena — lógica discreta")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18)
    small_font = pygame.font.SysFont("consolas", 14)
    atlas = SpriteAtlas(pygame, cell_size)

    render_fps = max(engine.config.ticks_per_second, render_fps)
    frames_per_tick = max(2, round(render_fps / engine.config.ticks_per_second))
    running = True
    notice: str | None = None
    notice_frames = 0
    last_snapshot = capture_snapshot(engine)

    while running and not engine.game_over:
        running = _handle_window_events(pygame)
        if not running:
            break

        before = last_snapshot
        actions = {
            player.player_id: controllers[player.player_id].decide(
                engine.observation_for(player.player_id)
            )
            for player in engine.alive_players()
        }
        engine.step(actions)
        after = capture_snapshot(engine)
        transition = VisualTransition(before, after, tuple(dict(e) for e in engine.events))
        last_snapshot = after

        new_notice = _notice_from_events(engine.events)
        if new_notice:
            notice = new_notice
            notice_frames = render_fps * 3

        for frame_number in range(frames_per_tick):
            running = _handle_window_events(pygame)
            if not running:
                break
            progress = (frame_number + 1) / frames_per_tick
            if notice_frames > 0:
                notice_frames -= 1
            else:
                notice = None
            _draw_scene(
                pygame,
                screen,
                font,
                small_font,
                atlas,
                engine,
                transition,
                progress,
                cell_size,
                panel_height,
                notice,
            )
            pygame.display.flip()
            clock.tick(render_fps)

    if running and engine.game_over:
        static_transition = VisualTransition(last_snapshot, last_snapshot, tuple())
        for _ in range(render_fps * 3):
            if not _handle_window_events(pygame):
                break
            _draw_scene(
                pygame,
                screen,
                font,
                small_font,
                atlas,
                engine,
                static_transition,
                1.0,
                cell_size,
                panel_height,
                notice,
            )
            pygame.display.flip()
            clock.tick(render_fps)

    pygame.quit()


def _handle_window_events(pygame) -> bool:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
    return True


def _notice_from_events(events: list[dict]) -> str | None:
    reason_labels = {
        "bomb_blast": "atingido diretamente pela explosão",
        "lingering_flame": "permaneceu sobre uma chama ativa",
        "arena_shrink": "atingido pelo fechamento da arena",
    }
    for event in reversed(events):
        if event.get("type") != "player_eliminated":
            continue
        player = int(event["player"]) + 1
        x, y = event.get("position", ("?", "?"))
        reason = reason_labels.get(event.get("reason"), str(event.get("reason")))
        bomb = event.get("bomb_id")
        suffix = f" Bomba #{bomb}." if bomb is not None else ""
        return f"P{player} eliminado em ({x}, {y}): {reason}.{suffix}"
    return None


def _direction(action: str | Action) -> str:
    try:
        action = Action(action)
    except ValueError:
        return "down"
    return {
        Action.UP: "up",
        Action.DOWN: "down",
        Action.LEFT: "left",
        Action.RIGHT: "right",
    }.get(action, "down")


def _flame_part(pos: tuple[int, int], flames: set[tuple[int, int]], bomb_positions: set[tuple[int, int]]) -> str:
    if pos in bomb_positions:
        return "center"
    x, y = pos
    left = (x - 1, y) in flames
    right = (x + 1, y) in flames
    up = (x, y - 1) in flames
    down = (x, y + 1) in flames
    horizontal = left or right
    vertical = up or down
    if horizontal and vertical:
        return "center"
    if left and right:
        return "horizontal"
    if up and down:
        return "vertical"
    if right and not left:
        return "end_left"
    if left and not right:
        return "end_right"
    if down and not up:
        return "end_up"
    if up and not down:
        return "end_down"
    return "center"


def _draw_scene(
    pygame,
    screen,
    font,
    small_font,
    atlas: SpriteAtlas,
    engine,
    transition: VisualTransition,
    progress: float,
    cell_size: int,
    panel_height: int,
    notice: str | None,
) -> None:
    screen.fill((28, 31, 38))
    snapshot = transition.phase_snapshot(progress)
    _draw_board(screen, atlas, snapshot, cell_size)
    _draw_items(screen, atlas, snapshot, cell_size)
    _draw_flames(screen, atlas, snapshot, progress, cell_size)
    _draw_bombs(screen, atlas, snapshot, engine, progress, cell_size)
    _draw_players(pygame, screen, atlas, transition, snapshot, progress, cell_size)
    _draw_hud(pygame, screen, font, small_font, engine, cell_size, panel_height, notice)
    _draw_elimination_markers(pygame, screen, transition, progress, cell_size)
    _draw_game_over(pygame, screen, engine, cell_size)


def _draw_board(screen, atlas: SpriteAtlas, snapshot: RenderSnapshot, cell_size: int) -> None:
    tile_names = {
        Tile.FLOOR: "floor.png",
        Tile.WALL: "wall.png",
        Tile.CRATE: "crate.png",
        Tile.SHRINK_WALL: "shrink_wall.png",
    }
    for y, row in enumerate(snapshot.grid):
        for x, raw_tile in enumerate(row):
            image = atlas.get(tile_names[Tile(raw_tile)])
            screen.blit(image, (x * cell_size, y * cell_size))


def _draw_items(screen, atlas: SpriteAtlas, snapshot: RenderSnapshot, cell_size: int) -> None:
    item_names = {
        ItemType.BOMB_UP: "item_bomb_up.png",
        ItemType.RANGE_UP: "item_range_up.png",
        ItemType.SPEED_UP: "item_speed_up.png",
        ItemType.SHIELD: "item_shield.png",
        ItemType.CURSE: "item_curse.png",
    }
    item_size = max(22, int(cell_size * 0.72))
    for item in snapshot.items:
        image = atlas.get(item_names[ItemType(item["type"])], (item_size, item_size))
        x = int(item["x"]) * cell_size + (cell_size - item_size) // 2
        y = int(item["y"]) * cell_size + (cell_size - item_size) // 2
        screen.blit(image, (x, y))


def _draw_flames(
    screen,
    atlas: SpriteAtlas,
    snapshot: RenderSnapshot,
    progress: float,
    cell_size: int,
) -> None:
    flame_positions = {(int(f["x"]), int(f["y"])) for f in snapshot.flames}
    bomb_positions = {
        tuple(f["bomb_position"])
        for f in snapshot.flames
        if f.get("bomb_position") is not None
    }
    pulse = int(progress * 6) % 2
    for flame in snapshot.flames:
        pos = int(flame["x"]), int(flame["y"])
        part = _flame_part(pos, flame_positions, bomb_positions)
        frame = FLAME_PART_OFFSETS[part] + pulse
        image = atlas.get_sheet_frame("flames.png", frame)
        screen.blit(image, (pos[0] * cell_size, pos[1] * cell_size))


def _draw_bombs(
    screen,
    atlas: SpriteAtlas,
    snapshot: RenderSnapshot,
    engine,
    progress: float,
    cell_size: int,
) -> None:
    for bomb in snapshot.bombs:
        remaining = max(0, int(bomb["explode_tick"]) - snapshot.tick)
        if remaining <= max(2, engine.config.ticks_per_second // 2):
            frame = 2
        else:
            frame = int((snapshot.tick + progress) * 2) % 2
        image = atlas.get_sheet_frame("bomb.png", frame)
        screen.blit(image, (int(bomb["x"]) * cell_size, int(bomb["y"]) * cell_size))


def _draw_players(
    pygame,
    screen,
    atlas: SpriteAtlas,
    transition: VisualTransition,
    snapshot: RenderSnapshot,
    progress: float,
    cell_size: int,
) -> None:
    player_size = max(28, int(cell_size * 0.96))
    for player_id in sorted(transition.after.players):
        if not transition.player_visible(player_id, progress):
            continue
        visual = snapshot.players[player_id]
        x_cell, y_cell = transition.player_position(player_id, progress)
        before = transition.before.players[player_id]
        after = transition.after.players[player_id]
        moving = before.pos != after.pos and progress < transition.movement_phase_end
        direction = _direction(after.last_effective_action)
        walk_frame = min(2, int(progress * 6) % 3) if moving else 1
        sheet_index = DIRECTION_OFFSETS[direction] + walk_frame
        image = atlas.get_sheet_frame(
            f"player_{player_id + 1}.png", sheet_index, (player_size, player_size)
        )
        x = round(x_cell * cell_size + (cell_size - player_size) / 2)
        y = round(y_cell * cell_size + cell_size - player_size)
        screen.blit(image, (x, y))

        center = (
            round(x_cell * cell_size + cell_size / 2),
            round(y_cell * cell_size + cell_size / 2),
        )
        if visual.cursed:
            pygame.draw.circle(screen, (235, 40, 235), center, cell_size // 2 - 1, 3)
            curse = atlas.get("item_curse.png", (16, 16))
            screen.blit(curse, (x + player_size - 16, y))
        if visual.shields:
            pygame.draw.circle(screen, (120, 220, 255), center, cell_size // 2, 3)


def _draw_elimination_markers(pygame, screen, transition: VisualTransition, progress: float, cell_size: int) -> None:
    if progress < transition.elimination_phase_start:
        return
    for event in transition.events:
        if event.get("type") != "player_eliminated":
            continue
        x, y = event["position"]
        center = (x * cell_size + cell_size // 2, y * cell_size + cell_size // 2)
        radius = max(7, int(cell_size * 0.28 * (1.2 - progress)))
        pygame.draw.circle(screen, (255, 245, 210), center, radius, 3)
        pygame.draw.line(
            screen,
            (90, 20, 20),
            (center[0] - radius, center[1] - radius),
            (center[0] + radius, center[1] + radius),
            3,
        )
        pygame.draw.line(
            screen,
            (90, 20, 20),
            (center[0] + radius, center[1] - radius),
            (center[0] - radius, center[1] + radius),
            3,
        )


def _draw_hud(
    pygame,
    screen,
    font,
    small_font,
    engine,
    cell_size: int,
    panel_height: int,
    notice: str | None,
) -> None:
    panel_y = engine.height * cell_size
    pygame.draw.rect(
        screen,
        (18, 20, 25),
        pygame.Rect(0, panel_y, engine.width * cell_size, panel_height),
    )
    time_left = max(0, engine.config.max_ticks - engine.tick) / engine.config.ticks_per_second
    shrink_in = engine._ticks_to_next_shrink()
    shrink_seconds = None if shrink_in is None else shrink_in / engine.config.ticks_per_second
    shrink_label = "--" if shrink_seconds is None else f"{shrink_seconds:4.1f}s"
    header = (
        f"tick={engine.tick}  restante={time_left:5.1f}s  "
        f"fechamento em={shrink_label}  margem={engine.shrink_margin}"
    )
    screen.blit(font.render(header, True, (240, 240, 240)), (10, panel_y + 8))

    for index, player in enumerate(engine.players.values()):
        marker = "VIVO" if player.alive else "FORA"
        curse = " CURSE" if player.cursed else ""
        text = (
            f"P{player.player_id + 1}:{player.name} {marker} pts={player.score} "
            f"K={player.kills} B={player.active_bombs}/{player.max_bombs}{curse}"
        )
        x = 10 + (index % 2) * (engine.width * cell_size // 2)
        y = panel_y + 39 + (index // 2) * 24
        screen.blit(small_font.render(text[:64], True, PLAYER_COLORS[index]), (x, y))

    if notice:
        box = pygame.Rect(8, panel_y + panel_height - 29, engine.width * cell_size - 16, 23)
        pygame.draw.rect(screen, (92, 34, 34), box, border_radius=4)
        screen.blit(small_font.render(notice, True, (255, 235, 220)), (14, box.y + 4))


def _draw_game_over(pygame, screen, engine, cell_size: int) -> None:
    if not engine.game_over or not engine.result:
        return
    overlay = pygame.Surface((engine.width * cell_size, engine.height * cell_size), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))
    winners = engine.result.winner_ids
    text = "EMPATE" if len(winners) != 1 else f"VENCEDOR: P{winners[0] + 1}"
    title = pygame.font.SysFont("consolas", 42, bold=True).render(text, True, (255, 255, 255))
    screen.blit(
        title,
        title.get_rect(center=(engine.width * cell_size // 2, engine.height * cell_size // 2)),
    )
