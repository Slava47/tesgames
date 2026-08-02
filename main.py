from __future__ import annotations

import math
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent
PLAYER_SHEET = ROOT / "player.jpg"
WORLD_IMAGE = ROOT / "world.png"

WINDOW_SIZE = (960, 540)
FPS = 60
BG_THRESHOLD = 245
PLAYER_SIZE = (84, 110)

# Должны совпадать с домами на world.png
BUILDING_RECTS = [
    pygame.Rect(80, 90, 190, 130),
    pygame.Rect(610, 80, 210, 160),
    pygame.Rect(130, 340, 210, 160),
    pygame.Rect(560, 320, 300, 180),
]


def _is_fg(color: pygame.Color) -> bool:
    return color.r < BG_THRESHOLD or color.g < BG_THRESHOLD or color.b < BG_THRESHOLD


def _find_segments(counts: list[int], min_pixels: int, min_size: int = 24) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(counts):
        if value >= min_pixels and start is None:
            start = i
        elif value < min_pixels and start is not None:
            if i - start >= min_size:
                segments.append((start, i - 1))
            start = None
    if start is not None and len(counts) - start >= min_size:
        segments.append((start, len(counts) - 1))
    return segments


def _trim_frame(surface: pygame.Surface) -> pygame.Surface:
    w, h = surface.get_size()
    min_x, min_y = w, h
    max_x, max_y = -1, -1

    for y in range(h):
        for x in range(w):
            if _is_fg(surface.get_at((x, y))):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if max_x < min_x or max_y < min_y:
        return pygame.Surface((1, 1), pygame.SRCALPHA)

    cut = pygame.Surface((max_x - min_x + 1, max_y - min_y + 1), pygame.SRCALPHA)
    cut.blit(surface, (0, 0), pygame.Rect(min_x, min_y, cut.get_width(), cut.get_height()))

    cleaned = pygame.Surface(cut.get_size(), pygame.SRCALPHA)
    for y in range(cut.get_height()):
        for x in range(cut.get_width()):
            color = cut.get_at((x, y))
            if _is_fg(color):
                cleaned.set_at((x, y), pygame.Color(color.r, color.g, color.b, 255))
            else:
                cleaned.set_at((x, y), pygame.Color(0, 0, 0, 0))
    return cleaned


def extract_frames(sheet_path: Path) -> list[list[pygame.Surface]]:
    sheet = pygame.image.load(str(sheet_path)).convert()
    w, h = sheet.get_size()

    row_counts = []
    for y in range(h):
        cnt = 0
        for x in range(w):
            if _is_fg(sheet.get_at((x, y))):
                cnt += 1
        row_counts.append(cnt)

    col_counts = []
    for x in range(w):
        cnt = 0
        for y in range(h):
            if _is_fg(sheet.get_at((x, y))):
                cnt += 1
        col_counts.append(cnt)

    row_segments = _find_segments(row_counts, min_pixels=20)
    col_segments = _find_segments(col_counts, min_pixels=20)

    if not row_segments or not col_segments:
        raise RuntimeError("Не удалось вырезать кадры из player.jpg")

    frames_by_row: list[list[pygame.Surface]] = []
    for y0, y1 in row_segments:
        row_frames: list[pygame.Surface] = []
        for x0, x1 in col_segments:
            frame = pygame.Surface((x1 - x0 + 1, y1 - y0 + 1))
            frame.blit(sheet, (0, 0), pygame.Rect(x0, y0, x1 - x0 + 1, y1 - y0 + 1))
            row_frames.append(_trim_frame(frame))
        frames_by_row.append(row_frames)

    return frames_by_row


def pick_animations(rows: list[list[pygame.Surface]]) -> dict[str, list[pygame.Surface]]:
    idle_row = 2 if len(rows) > 2 else 0
    walk_row = 3 if len(rows) > 3 else max(0, len(rows) - 1)
    run_row = 4 if len(rows) > 4 else walk_row
    jump_row = 5 if len(rows) > 5 else max(0, len(rows) - 1)

    def non_empty(values: list[pygame.Surface]) -> list[pygame.Surface]:
        return [frame for frame in values if frame.get_width() > 1 and frame.get_height() > 1]

    idle = non_empty(rows[idle_row])
    walk = non_empty(rows[walk_row])
    run = non_empty(rows[run_row])
    jump = non_empty(rows[jump_row])

    if not idle:
        idle = walk or run or jump
    if not walk:
        walk = idle
    if not run:
        run = walk
    if not jump:
        jump = idle

    return {"idle": idle, "walk": walk, "run": run, "jump": jump}


def scaled_frames(frames: list[pygame.Surface]) -> list[pygame.Surface]:
    return [pygame.transform.smoothscale(frame, PLAYER_SIZE) for frame in frames]


def get_hitbox(pos: pygame.Vector2) -> pygame.Rect:
    return pygame.Rect(int(pos.x + 24), int(pos.y + 76), 36, 30)


def move_with_collisions(pos: pygame.Vector2, delta: pygame.Vector2, solids: list[pygame.Rect]) -> pygame.Vector2:
    pos.x += delta.x
    hitbox = get_hitbox(pos)
    for solid in solids:
        if hitbox.colliderect(solid):
            if delta.x > 0:
                hitbox.right = solid.left
            elif delta.x < 0:
                hitbox.left = solid.right
            pos.x = hitbox.x - 24

    pos.y += delta.y
    hitbox = get_hitbox(pos)
    for solid in solids:
        if hitbox.colliderect(solid):
            if delta.y > 0:
                hitbox.bottom = solid.top
            elif delta.y < 0:
                hitbox.top = solid.bottom
            pos.y = hitbox.y - 76

    pos.x = max(-10, min(pos.x, WINDOW_SIZE[0] - PLAYER_SIZE[0] + 10))
    pos.y = max(-10, min(pos.y, WINDOW_SIZE[1] - PLAYER_SIZE[1] + 8))
    return pos


def main() -> int:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Mini World")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 20)

    world = pygame.image.load(str(WORLD_IMAGE)).convert()
    world = pygame.transform.smoothscale(world, WINDOW_SIZE)

    animations_raw = pick_animations(extract_frames(PLAYER_SHEET))
    animations = {key: scaled_frames(value) for key, value in animations_raw.items()}

    pos = pygame.Vector2(460, 260)
    facing_left = False

    walk_timer = 0.0
    jump_timer = 0.0
    jump_duration = 0.55
    is_jumping = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                if not is_jumping:
                    is_jumping = True
                    jump_timer = 0.0

        keys = pygame.key.get_pressed()
        move = pygame.Vector2(0, 0)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move.x += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move.y += 1

        speed = 250 if (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) else 165
        if move.length_squared() > 0:
            move = move.normalize()
            facing_left = move.x < 0 or (move.x == 0 and facing_left)
            pos = move_with_collisions(pos, move * speed * dt, BUILDING_RECTS)
            walk_timer += dt
        else:
            walk_timer = 0.0

        if is_jumping:
            jump_timer += dt
            if jump_timer >= jump_duration:
                is_jumping = False
                jump_timer = 0.0

        if is_jumping:
            frames = animations["jump"]
            progress = min(1.0, jump_timer / jump_duration)
            frame_index = min(len(frames) - 1, int(progress * len(frames)))
            jump_height = math.sin(progress * math.pi) * 34
            state = "jump"
        elif move.length_squared() == 0:
            frames = animations["idle"]
            frame_index = 0
            jump_height = 0
            state = "idle"
        else:
            state = "run" if speed > 200 else "walk"
            frames = animations[state]
            frame_index = int(walk_timer / (0.09 if state == "run" else 0.13)) % len(frames)
            jump_height = 0

        frame = frames[frame_index]
        if facing_left:
            frame = pygame.transform.flip(frame, True, False)

        screen.blit(world, (0, 0))

        shadow = pygame.Surface((42, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (20, 20, 20, 90), shadow.get_rect())
        shadow_pos = (pos.x + 21, pos.y + 90)
        screen.blit(shadow, shadow_pos)

        screen.blit(frame, (pos.x, pos.y - jump_height))

        hint = font.render("Move: WASD / Arrows | Run: Shift | Jump: Space", True, (26, 26, 26))
        screen.blit(hint, (16, 14))
        status = font.render(f"State: {state}", True, (26, 26, 26))
        screen.blit(status, (16, 38))

        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
