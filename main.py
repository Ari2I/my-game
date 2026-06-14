"""
main.py — точка входа.

Горячие клавиши в игре:
  ESC   — главное меню
  F3    — счётчик FPS
  F4    — отладка: показать коллизионные стены (красные рамки)
  F5    — отладка: показать конус атаки игрока
  H     — (DEBUG) -10 HP
  X     — (DEBUG) +50 XP, +1 слизь
  Q     — (DEBUG) заспавнить 3 слайма
"""

import pygame
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.map    import TileMap, get_content_bounds
from core.player import Player
from core.hud    import HUD
from core.menu   import MainMenu
from core.slime  import SlimeManager
from core.walls  import WallMap

WIDTH      = 1920
HEIGHT     = 1080
TARGET_FPS = 120

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Cursed Land")
clock = pygame.time.Clock()

font_fps  = pygame.font.SysFont(None, 26)
font_dbg  = pygame.font.SysFont(None, 22)

show_fps   = False
show_walls = False
show_cone  = False


# ── кешированная карта ────────────────────────────────────────────────────────
class CachedTileMap(TileMap):
    def __init__(self, filename):
        super().__init__(filename)
        self._cache: dict = {}

    def _get_scaled(self, gid):
        if gid not in self._cache:
            tile = self.tmx_data.get_tile_image_by_gid(gid)
            self._cache[gid] = (
                pygame.transform.scale(tile, (self.tile_width, self.tile_height))
                if tile else None
            )
        return self._cache[gid]

    def draw(self, screen, camera_x=0, camera_y=0):
        import pytmx
        sw, sh = screen.get_size()
        for layer in self.tmx_data.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid in layer:
                    tx = x * self.tile_width  - camera_x
                    ty = y * self.tile_height - camera_y
                    if tx > sw or ty > sh or tx < -self.tile_width or ty < -self.tile_height:
                        continue
                    scaled = self._get_scaled(gid)
                    if scaled:
                        screen.blit(scaled, (tx, ty))


# ── игровой цикл ──────────────────────────────────────────────────────────────
def run_game(save_path=None):
    global show_fps, show_walls, show_cone

    # ── загрузка карты ────────────────────────────────────────────────────────
    game_map = CachedTileMap("images/maps/mapV1.tmx")
    map_w_px = game_map.tmx_data.width  * game_map.tile_width
    map_h_px = game_map.tmx_data.height * game_map.tile_height

    # ── реальные границы отрисованного контента карты ──────────────────────────
    # (нужны для корректного спавна слаймов — номинальный tmx-грид может
    # содержать пустые края)
    content_x0, content_y0, content_x1, content_y1 = get_content_bounds(
        game_map.tmx_data, game_map.tile_width, game_map.tile_height)

    # ── стены ─────────────────────────────────────────────────────────────────
    wall_map = WallMap(game_map.tmx_data, game_map.tile_width, game_map.tile_height)

    # ── игрок ─────────────────────────────────────────────────────────────────
    player = Player(map_w_px // 3, map_h_px // 3)

    if save_path:
        import json
        try:
            with open(save_path) as f:
                player.from_dict(json.load(f))
        except Exception as e:
            print(f"[game] Ошибка загрузки: {e}")

    hud    = HUD(WIDTH, HEIGHT)
    slimes = SlimeManager(map_w_px, map_h_px)
    slimes.set_spawn_area(content_x0, content_y0, content_x1, content_y1)
    slimes.spawn_wave(wave=1, count=5)

    # ── DEBUG данные ──────────────────────────────────────────────────────────
    player.inventory.slime_goo = 5
    player.gain_xp(80)

    while True:
        raw_ms = clock.tick(TARGET_FPS)
        dt = min(raw_ms / (1000.0 / TARGET_FPS), 4.0)

        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:  return "menu"
                if event.key == pygame.K_F3:      show_fps   = not show_fps
                if event.key == pygame.K_F4:      show_walls = not show_walls
                if event.key == pygame.K_F5:      show_cone  = not show_cone
                # DEBUG
                if event.key == pygame.K_h:       player.take_damage(10)
                if event.key == pygame.K_x:
                    player.gain_xp(50)
                    player.inventory.slime_goo += 1
                if event.key == pygame.K_q:       slimes.spawn_wave(wave=1, count=3)

            hud.handle_event(event, player)

        hud.update(mouse_pos)

        # ── обновление игрока ─────────────────────────────────────────────────
        keys = pygame.key.get_pressed()
        player.update_player(keys, dt)

        # Разрешение коллизий со стенами
        wall_map.resolve_player(player.rect)

        # Атака — наносим урон слаймам в конусе в активной фазе анимации
        player.try_deal_attack(slimes)

        # ── обновление слаймов ────────────────────────────────────────────────
        slimes.update(player, dt)

        # Разрешаем коллизии слаймов со стенами
        for slime in slimes.slimes:
            wall_map.resolve_entity(slime.rect)
            slime.x = float(slime.rect.centerx)
            slime.y = float(slime.rect.centery)

        # ── камера ────────────────────────────────────────────────────────────
        camera_x = max(0, min(player.rect.centerx - WIDTH  // 2, map_w_px - WIDTH))
        camera_y = max(0, min(player.rect.centery - HEIGHT // 2, map_h_px - HEIGHT))

        # ── отрисовка ─────────────────────────────────────────────────────────
        screen.fill((39, 42, 57))
        game_map.draw(screen, camera_x, camera_y)

        if show_walls:
            wall_map.debug_draw(screen, camera_x, camera_y)

        slimes.draw(screen, camera_x, camera_y)

        if show_cone:
            player.draw_attack_cone(screen, camera_x, camera_y)

        player.draw(screen, camera_x, camera_y)

        # i-frame мигание игрока
        if player.is_invincible and int(pygame.time.get_ticks() / 80) % 2 == 0:
            flash = pygame.Surface(player.rect.size, pygame.SRCALPHA)
            flash.fill((255, 255, 255, 60))
            screen.blit(flash, (player.rect.x - camera_x, player.rect.y - camera_y))

        hud.draw(screen, player)

        if show_fps:
            fps_s = font_fps.render(f"FPS: {clock.get_fps():.0f}  |  "
                                    f"Слаймов: {slimes.count}", True, (255, 220, 60))
            screen.blit(fps_s, (10, 10))

        if show_walls or show_cone:
            hint = font_dbg.render("F4=стены  F5=конус", True, (150, 150, 150))
            screen.blit(hint, (10, 36))

        pygame.display.flip()


# ── главный цикл ─────────────────────────────────────────────────────────────
def main():
    while True:
        menu   = MainMenu(screen)
        result = menu.run()

        if result == "quit":
            break

        save    = result[len("load:"):] if result.startswith("load:") else None
        outcome = run_game(save_path=save)

        if outcome == "quit":
            break

    pygame.quit()


if __name__ == "__main__":
    main()