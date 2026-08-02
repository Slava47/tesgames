from __future__ import annotations

from pathlib import Path
import sys

import pygame


ROOT = Path(__file__).resolve().parent
PLAYER_SHEET = ROOT / "player.jpg"
WORLD_IMAGE = ROOT / "world.png"
SPRITES_DIR = ROOT / "sprites" / "player"
WINDOW_SIZE = (960, 540)
FPS = 60


def extract_player_sprites(sheet_path: Path, out_dir: Path, cols: int = 3, rows: int = 4) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if any(out_dir.glob("frame_*.png")):
        return

    sheet = pygame.image.load(str(sheet_path)).convert_alpha()
    frame_w = sheet.get_width() // cols
    frame_h = sheet.get_height() // rows

    frame_index = 0
    for row in range(rows):
        for col in range(cols):
            rect = pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
            frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), rect)
            pygame.image.save(frame, str(out_dir / f"frame_{frame_index:02d}.png"))
            frame_index += 1


def load_animation_frames(out_dir: Path) -> dict[str, list[pygame.Surface]]:
    frames = [pygame.image.load(str(path)).convert_alpha() for path in sorted(out_dir.glob("frame_*.png"))]
    if not frames:
        raise RuntimeError("No player frames were extracted.")

    animations = {
        "idle": frames[0:3] or frames[:1],
        "walk": frames[3:6] or frames[:1],
        "jump": frames[6:9] or frames[:1],
    }
    for key, value in list(animations.items()):
        if not value:
            animations[key] = frames[:1]
    return animations


def try_load_world() -> pygame.Surface | None:
    try:
        image = pygame.image.load(str(WORLD_IMAGE)).convert()
    except Exception:
        return None
    return pygame.transform.smoothscale(image, WINDOW_SIZE)


def main() -> int:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Mini RPG")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 24)

    extract_player_sprites(PLAYER_SHEET, SPRITES_DIR)
    animations = load_animation_frames(SPRITES_DIR)
    world_surface = try_load_world()

    player_pos = pygame.Vector2(140, 120)
    player_vel = pygame.Vector2(0, 0)
    speed = 280
    gravity = 1700
    jump_force = -650
    frame_timer = 0.0
    frame_idx = 0
    facing_left = False
    on_ground = False

    platforms = [
        pygame.Rect(0, WINDOW_SIZE[1] - 64, WINDOW_SIZE[0], 64),
        pygame.Rect(240, 380, 180, 20),
        pygame.Rect(500, 300, 180, 20),
        pygame.Rect(740, 220, 140, 20),
    ]

    running = True
    while running:
        dt = clock.tick(FPS) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        move_x = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move_x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move_x += 1
        if move_x:
            facing_left = move_x < 0

        player_vel.x = move_x * speed
        if (keys[pygame.K_w] or keys[pygame.K_SPACE] or keys[pygame.K_UP]) and on_ground:
            player_vel.y = jump_force
            on_ground = False
        player_vel.y += gravity * dt
        player_pos += player_vel * dt

        active_frame = animations["idle"][0]
        player_size = pygame.Vector2(active_frame.get_width() // 3, active_frame.get_height() // 3)
        player_rect = pygame.Rect(int(player_pos.x), int(player_pos.y), int(player_size.x), int(player_size.y))

        on_ground = False
        for platform in platforms:
            if player_rect.colliderect(platform) and player_vel.y >= 0:
                if player_rect.bottom - player_vel.y * dt <= platform.top + 10:
                    player_rect.bottom = platform.top
                    player_pos.y = player_rect.y
                    player_vel.y = 0
                    on_ground = True

        player_pos.x = max(0, min(player_pos.x, WINDOW_SIZE[0] - player_rect.width))
        if player_pos.y > WINDOW_SIZE[1]:
            player_pos.update(140, 120)
            player_vel.update(0, 0)

        if not on_ground:
            state = "jump"
        elif move_x:
            state = "walk"
        else:
            state = "idle"

        frame_timer += dt
        if frame_timer >= 0.12:
            frame_timer = 0
            frame_idx = (frame_idx + 1) % len(animations[state])

        frame = animations[state][frame_idx % len(animations[state])]
        frame = pygame.transform.scale(frame, (int(player_size.x), int(player_size.y)))
        if facing_left:
            frame = pygame.transform.flip(frame, True, False)

        if world_surface is not None:
            screen.blit(world_surface, (0, 0))
        else:
            screen.fill((92, 168, 255))
        for platform in platforms:
            pygame.draw.rect(screen, (58, 58, 72), platform, border_radius=8)
        screen.blit(frame, (player_pos.x, player_pos.y))

        tip = font.render("A/D or ←/→: move | W/Space/↑: jump", True, (20, 20, 20))
        screen.blit(tip, (18, 16))
        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
