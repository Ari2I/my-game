"""
main.py — точка входа.

Горячие клавиши в игре:
  ESC   — главное меню
  F3    — счётчик FPS
  F4    — отладка: показать коллизионные стены + хитбокс игрока
  F5    — отладка: показать конус атаки игрока
  H     — (DEBUG) -10 HP
  X     — (DEBUG) +50 XP, +1 слизь
  Q     — (DEBUG) заспавнить 3 слайма
  E     — (DEBUG) заспавнить 1 дальнего врага
"""

import pygame
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.map import TileMap
from core.player import Player, HITBOX_OFFSET_Y
from core.hud import HUD
from core.menu import MainMenu
from core.slime import SlimeManager
from core.ranged_enemy import RangedEnemyManager
from core.wave_manager import WaveManager
from core.walls import WallMap

from core.render.player_renderer import PlayerRenderer
from core.render.slime_renderer import SlimeManagerRenderer
from core.render.ranged_enemy_renderer import RangedEnemyManagerRenderer

WIDTH = 1920
HEIGHT = 1080
TARGET_FPS = 120

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Cursed Land")
clock = pygame.time.Clock()

font_fps = pygame.font.SysFont(None, 26)
font_dbg = pygame.font.SysFont(None, 22)

show_fps = False
show_walls = False
show_cone = False


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
                    tx = x * self.tile_width - camera_x
                    ty = y * self.tile_height - camera_y
                    if tx > sw or ty > sh or tx < -self.tile_width or ty < -self.tile_height:
                        continue
                    scaled = self._get_scaled(gid)
                    if scaled:
                        screen.blit(scaled, (tx, ty))


# ── вспомогательный адаптер для try_deal_attack ───────────────────────────────
class _CombinedEnemyView:
    """
    Позволяет player.try_deal_attack работать со всеми врагами сразу.
    Объединяет enemies из SlimeManager и RangedEnemyManager в один список.
    Принцип ISP: Player видит только интерфейс .enemies.
    """

    def __init__(self, slime_mgr, ranged_mgr):
        self._slime_mgr = slime_mgr
        self._ranged_mgr = ranged_mgr

    @property
    def enemies(self) -> list:
        return self._slime_mgr.enemies + self._ranged_mgr.enemies


# ── игровой цикл ──────────────────────────────────────────────────────────────
def run_game(save_path=None):
    global show_fps, show_walls, show_cone

    game_map = CachedTileMap("images/maps/mapV1.tmx")
    map_w_px = game_map.tmx_data.width * game_map.tile_width
    map_h_px = game_map.tmx_data.height * game_map.tile_height

    wall_map = WallMap(game_map.tmx_data, game_map.tile_width, game_map.tile_height)

    player = Player(map_w_px // 3, map_h_px // 3)

    if save_path:
        import json
        try:
            with open(save_path) as f:
                player.from_dict(json.load(f))
        except Exception as e:
            print(f"[game] Ошибка загрузки: {e}")

    hud = HUD(WIDTH, HEIGHT)
    slimes = SlimeManager(map_w_px, map_h_px)
    ranged = RangedEnemyManager(map_w_px, map_h_px)

    # WaveManager управляет волнами обоих менеджеров
    wave_mgr = WaveManager(slimes, ranged)

    # Адаптер для единого apply_damage из player
    all_enemies = _CombinedEnemyView(slimes, ranged)

    player_renderer = PlayerRenderer(player)
    slime_renderer = SlimeManagerRenderer()
    ranged_renderer = RangedEnemyManagerRenderer()

    # Debug стартовые данные
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
                if event.key == pygame.K_F3:      show_fps = not show_fps
                if event.key == pygame.K_F4:      show_walls = not show_walls
                if event.key == pygame.K_F5:      show_cone = not show_cone
                if event.key == pygame.K_h:       player.take_damage(10)
                if event.key == pygame.K_x:
                    player.gain_xp(50)
                    player.inventory.add_item("slime_goo", 1)
                if event.key == pygame.K_q:
                    slimes.spawn_wave(wave=wave_mgr.wave or 1, count=3)
                if event.key == pygame.K_e:
                    ranged.spawn_one(wave=wave_mgr.wave or 1)

            hud.handle_event(event, player)

        hud.update(mouse_pos)

        # ── обновление волн ───────────────────────────────────────────────────
        wave_mgr.update(dt)

        # ── обновление игрока ─────────────────────────────────────────────────
        keys = pygame.key.get_pressed()
        player.update_player(keys, dt)

        # Коллизия стен работает с hitbox
        wall_map.resolve_player(player.hitbox)
        player.world_x = float(player.hitbox.centerx)
        player.world_y = float(player.hitbox.centery) - HITBOX_OFFSET_Y
        player.rect.center = (int(player.world_x), int(player.world_y))

        player.try_deal_attack(all_enemies)

        # ── обновление слаймов ────────────────────────────────────────────────
        slimes.update(player, dt)
        for slime in slimes.enemies:
            wall_map.resolve_entity(slime.rect)
            slime.x = float(slime.rect.centerx)
            slime.y = float(slime.rect.centery)

        # ── обновление дальних врагов и снарядов ─────────────────────────────
        ranged.update(player, dt, wall_map)
        for enemy in ranged.enemies:
            wall_map.resolve_entity(enemy.rect)
            enemy.x = float(enemy.rect.centerx)
            enemy.y = float(enemy.rect.centery)

        # ── камера центрируется по hitbox ─────────────────────────────────────
        camera_x = max(0, min(player.hitbox.centerx - WIDTH // 2, map_w_px - WIDTH))
        camera_y = max(0, min(player.hitbox.centery - HEIGHT // 2, map_h_px - HEIGHT))

        # ── отрисовка ─────────────────────────────────────────────────────────
        screen.fill((39, 42, 57))
        game_map.draw(screen, camera_x, camera_y)

        if show_walls:
            wall_map.debug_draw(screen, camera_x, camera_y)

        slime_renderer.draw(slimes, screen, camera_x, camera_y)
        ranged_renderer.draw(ranged, screen, camera_x, camera_y)

        if show_cone:
            player_renderer.draw_attack_cone(screen, camera_x, camera_y)

        player_renderer.draw(screen, camera_x, camera_y)
        player_renderer.draw_iframe_flash(screen, camera_x, camera_y)

        # Отладка: зелёный хитбокс
        if show_walls:
            hb = player.hitbox.move(-camera_x, -camera_y)
            pygame.draw.rect(screen, (0, 255, 0), hb, 2)
            wx = int(player.world_x) - camera_x
            wy = int(player.world_y) - camera_y
            pygame.draw.line(screen, (255, 255, 255), (wx - 6, wy), (wx + 6, wy), 1)
            pygame.draw.line(screen, (255, 255, 255), (wx, wy - 6), (wx, wy + 6), 1)

        hud.draw(screen, player)

        # Волна в HUD (поверх)
        wave_surf = font_fps.render(
            f"Волна: {wave_mgr.wave}  |  Врагов: {wave_mgr.enemies_remaining}" +
            (f"  |  Следующая через {wave_mgr.time_until_next_wave:.1f}с"
             if wave_mgr.is_between_waves else ""),
            True, (200, 170, 80))
        screen.blit(wave_surf, (10, HEIGHT - 140))

        if show_fps:
            fps_s = font_fps.render(
                f"FPS: {clock.get_fps():.0f}  |  Слаймов: {slimes.count}"
                f"  |  Дальних: {ranged.count}",
                True, (255, 220, 60))
            screen.blit(fps_s, (10, 10))

        if show_walls or show_cone:
            hint = font_dbg.render(
                "F4=стены+хитбокс  F5=конус  Q=слаймы  E=дальний враг",
                True, (150, 150, 150))
            screen.blit(hint, (10, 36))

        pygame.display.flip()


# ── главный цикл ──────────────────────────────────────────────────────────────
def main():
    while True:
        menu = MainMenu(screen)
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
