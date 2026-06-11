"""
main.py — точка входа.

Стабилизация FPS:
  • clock.tick(TARGET_FPS) ограничивает частоту кадров.
  • Все движения и анимации умножаются на dt (delta-time),
    чтобы скорость не зависела от реального FPS.
  • Тяжёлые операции (масштабирование тайлов) кешируются в CachedTileMap.

Горячие клавиши в игре:
  ESC  — главное меню
  F3   — счётчик FPS
  H    — (DEBUG) -10 HP
  X    — (DEBUG) +50 XP, +1 слизь
"""

import pygame
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.map    import TileMap
from core.player import Player
from core.hud    import HUD
from core.menu   import MainMenu

WIDTH      = 1920
HEIGHT     = 1080
TARGET_FPS = 120

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Cursed Land")
clock  = pygame.time.Clock()

font_fps = pygame.font.SysFont(None, 26)
show_fps = False


class CachedTileMap(TileMap):
    """TileMap с кешем масштабированных тайлов — убирает основную просадку FPS."""

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


def run_game(save_path=None):
    global show_fps

    game_map = CachedTileMap("images/maps/mapV1.tmx")
    map_w_px = game_map.tmx_data.width  * game_map.tile_width
    map_h_px = game_map.tmx_data.height * game_map.tile_height

    player = Player(map_w_px // 2, map_h_px // 2)

    if save_path:
        import json
        try:
            with open(save_path) as f:
                player.from_dict(json.load(f))
        except Exception as e:
            print(f"[game] Ошибка загрузки: {e}")

    hud = HUD(WIDTH, HEIGHT)

    # ---- DEBUG данные для демонстрации ----
    player.inventory.slime_goo = 5
    player.gain_xp(80)
    # ----------------------------------------

    while True:
        raw_ms = clock.tick(TARGET_FPS)
        dt = raw_ms / (1000.0 / TARGET_FPS)
        dt = min(dt, 4.0)

        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "menu"
                if event.key == pygame.K_F3:
                    show_fps = not show_fps
                if event.key == pygame.K_h:
                    player.take_damage(10)
                if event.key == pygame.K_x:
                    player.gain_xp(50)
                    player.inventory.slime_goo += 1
            hud.handle_event(event, player)

        hud.update(mouse_pos)

        keys = pygame.key.get_pressed()
        player.update_player(keys, dt)

        camera_x = max(0, min(player.rect.centerx - WIDTH  // 2, map_w_px  - WIDTH))
        camera_y = max(0, min(player.rect.centery - HEIGHT // 2, map_h_px  - HEIGHT))

        screen.fill((39, 42, 57))
        game_map.draw(screen, camera_x, camera_y)
        player.draw(screen, camera_x, camera_y)
        hud.draw(screen, player)

        if show_fps:
            fps_surf = font_fps.render(f"FPS: {clock.get_fps():.0f}", True, (255, 220, 60))
            screen.blit(fps_surf, (10, 10))

        pygame.display.flip()


def main():
    while True:
        menu   = MainMenu(screen)
        result = menu.run()

        if result == "quit":
            break

        save = result[len("load:"):] if result.startswith("load:") else None
        outcome = run_game(save_path=save)

        if outcome == "quit":
            break

    pygame.quit()


if __name__ == "__main__":
    main()