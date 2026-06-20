"""
main.py — точка входа.

Горячие клавиши в игре:
  ESC   — пауза (PauseMenu)
  TAB   — инвентарь (InventoryPanel)
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
from core.pause_menu import PauseMenu
from core.inventory_ui import InventoryPanel
from core.intro_screen import IntroScreen
from core.audio import AudioManager
from core.slime import SlimeManager
from core.ranged_enemy import RangedEnemyManager
from core.wave_manager import WaveManager
from core.walls import WallMap

from core.render.player_renderer import PlayerRenderer
from core.render.slime_renderer import SlimeManagerRenderer
from core.render.ranged_enemy_renderer import RangedEnemyManagerRenderer
from core.render.y_sort_renderer import YSortRenderer

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
    """
    Расширяет TileMap кэшированием масштабированных тайлов по gid.

    Для Y-сортировки (персонаж то перед объектом, то за ним) переопределяет
    draw_ground() и iter_object_sprites() из базового класса так, чтобы они
    тоже использовали кэш — без этого сортировка по 60×60 тайлам объектных
    слоёв на каждый кадр была бы слишком медленной.

    iter_object_sprites() здесь ПЕРЕИСПОЛЬЗУЕТ группировку тайлов в связные
    блоки (self._get_object_groups(), унаследовано из TileMap, см.
    core/map.py) — без неё крупные многотайловые объекты карты (например,
    декоративные монументы на много тайлов) «разваливаются» при потайловой
    Y-сортировке: верхняя часть объекта считается «дальше» игрока, нижняя —
    «ближе», и персонаж оказывается визуально разрезан пополам относительно
    объекта. Группировка считается один раз и кэшируется в self._object_groups_cache
    (унаследованный кэш из TileMap), поэтому на FPS это не влияет.
    """

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
        """Старое поведение: рисует ВСЕ слои одним проходом (для меню/превью)."""
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

    def draw_ground(self, screen, camera_x=0, camera_y=0, layer_names=None):
        """Рисует только слои земли, с кэшированными тайлами + отсечением экрана."""
        import pytmx
        from core.map import GROUND_LAYER_NAMES
        names = layer_names if layer_names is not None else GROUND_LAYER_NAMES
        sw, sh = screen.get_size()
        for layer in self.tmx_data.visible_layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            if layer.name not in names:
                continue
            for x, y, gid in layer:
                tx = x * self.tile_width - camera_x
                ty = y * self.tile_height - camera_y
                if tx > sw or ty > sh or tx < -self.tile_width or ty < -self.tile_height:
                    continue
                scaled = self._get_scaled(gid)
                if scaled:
                    screen.blit(scaled, (tx, ty))

    def iter_object_sprites(self, layer_names=None):
        """
        Возвращает «высокие» тайлы (деревья/постройки/мосты/крупные
        многотайловые декорации) СГРУППИРОВАННЫМИ в связные блоки — для
        последующей Y-сортировки вместе с игроком/врагами.

        Группировка (flood fill по связности) переиспользуется из базового
        TileMap._get_object_groups() / _build_object_groups() (см.
        core/map.py — там же подробный докстринг о том, зачем группировка
        вообще нужна). Эта реализация отличается от базовой только тем, что
        берёт картинки тайлов из кэша self._get_scaled(gid) вместо
        pygame.transform.scale на каждый вызов.

        Формат результата (как и в базовом TileMap):
            [(y_sort_key, [(tile_image, world_x, world_y), ...]), ...]
        """
        from core.map import OBJECT_LAYER_NAMES
        names = layer_names if layer_names is not None else OBJECT_LAYER_NAMES
        groups = self._get_object_groups(names)

        result = []
        for group in groups:
            tiles_out = []
            max_bottom = None
            for tx, ty, gid in group["cells"]:
                scaled = self._get_scaled(gid)
                if not scaled:
                    continue
                world_x = tx * self.tile_width
                world_y = ty * self.tile_height
                tile_bottom = world_y + self.tile_height
                if max_bottom is None or tile_bottom > max_bottom:
                    max_bottom = tile_bottom
                tiles_out.append((scaled, world_x, world_y))

            if tiles_out:
                result.append((float(max_bottom), tiles_out))

        return result


# ── вспомогательный адаптер для try_deal_attack ───────────────────────────────
class _CombinedEnemyView:
    """
    Позволяет player.try_deal_attack работать со всеми врагами сразу.
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
    inv_panel = InventoryPanel(WIDTH, HEIGHT)
    pause_menu = PauseMenu(screen)
    audio = AudioManager()

    slimes = SlimeManager(map_w_px, map_h_px)
    ranged = RangedEnemyManager(map_w_px, map_h_px)
    wave_mgr = WaveManager(slimes, ranged)
    all_enemies = _CombinedEnemyView(slimes, ranged)

    player_renderer = PlayerRenderer(player)
    slime_renderer = SlimeManagerRenderer()
    ranged_renderer = RangedEnemyManagerRenderer()
    y_sort_renderer = YSortRenderer(player_renderer, slime_renderer, ranged_renderer)

    # Запускаем фоновую музыку (если файл есть)
    audio.play_music()

    # Debug стартовые данные
    player.inventory.slime_goo = 5
    player.gain_xp(80)

    # Состояние игры
    paused = False
    last_frame = pygame.Surface((WIDTH, HEIGHT))  # снимок последнего кадра для паузы

    while True:
        raw_ms = clock.tick(TARGET_FPS)
        dt = min(raw_ms / (1000.0 / TARGET_FPS), 4.0)
        mouse_pos = pygame.mouse.get_pos()

        # ── обработка событий ─────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if paused:
                pause_menu.update(mouse_pos)
                result = pause_menu.handle_event(event)
                if result == "resume":
                    paused = False
                elif result == "menu":
                    return "menu"
                elif result == "quit":
                    return "quit"
                continue  # пока пауза — игнорируем остальные события

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    paused = True
                    last_frame.blit(screen, (0, 0))  # снимок кадра для фона паузы

                if event.key == pygame.K_TAB:
                    inv_panel.toggle()

                if event.key == pygame.K_F3:   show_fps = not show_fps
                if event.key == pygame.K_F4:   show_walls = not show_walls
                if event.key == pygame.K_F5:   show_cone = not show_cone
                if event.key == pygame.K_h:    player.take_damage(10)
                if event.key == pygame.K_x:
                    player.gain_xp(50)
                    player.inventory.add_item("slime_goo", 1)
                if event.key == pygame.K_q:
                    slimes.spawn_wave(wave=wave_mgr.wave or 1, count=3)
                if event.key == pygame.K_e:
                    ranged.spawn_one(wave=wave_mgr.wave or 1)

            hud.handle_event(event, player)

        # ── если пауза — рисуем оверлей и переходим к следующему кадру ───────
        if paused:
            pause_menu.update(mouse_pos)
            pause_menu.draw(last_frame)
            pygame.display.flip()
            continue

        hud.update(mouse_pos)

        # ── обновление волн ───────────────────────────────────────────────────
        wave_mgr.update(dt)

        # ── обновление игрока ─────────────────────────────────────────────────
        keys = pygame.key.get_pressed()
        player.update_player(keys, dt)

        wall_map.resolve_player(player.hitbox)
        player.world_x = float(player.hitbox.centerx)
        player.world_y = float(player.hitbox.centery) - HITBOX_OFFSET_Y
        player.rect.center = (int(player.world_x), int(player.world_y))

        hit_any = player.try_deal_attack(all_enemies)
        if hit_any:
            audio.play_sfx("hit")

        # ── обновление слаймов ────────────────────────────────────────────────
        prev_slime_count = slimes.count
        slimes.update(player, dt)
        if slimes.count < prev_slime_count:
            audio.play_sfx("enemy_hurt")
        for slime in slimes.enemies:
            wall_map.resolve_entity(slime.rect)
            slime.x = float(slime.rect.centerx)
            slime.y = float(slime.rect.centery)

        # ── обновление дальних врагов и снарядов ─────────────────────────────
        prev_ranged_count = ranged.count
        ranged.update(player, dt, wall_map)
        if ranged.count < prev_ranged_count:
            audio.play_sfx("enemy_hurt")
        for enemy in ranged.enemies:
            wall_map.resolve_entity(enemy.rect)
            enemy.x = float(enemy.rect.centerx)
            enemy.y = float(enemy.rect.centery)

        # ── камера ────────────────────────────────────────────────────────────
        camera_x = max(0, min(player.hitbox.centerx - WIDTH // 2, map_w_px - WIDTH))
        camera_y = max(0, min(player.hitbox.centery - HEIGHT // 2, map_h_px - HEIGHT))

        # ── отрисовка ─────────────────────────────────────────────────────────
        screen.fill((39, 42, 57))

        # 1. Земля — всегда под всеми сущностями (вода, грунт, детали)
        game_map.draw_ground(screen, camera_x, camera_y)

        if show_walls:
            wall_map.debug_draw(screen, camera_x, camera_y)

        # 2. Y-сортированный проход: «высокие» тайлы карты (деревья, мосты,
        #    постройки) + игрок + слаймы + дальние враги — все вместе,
        #    в порядке Y-координаты нижней точки. Благодаря этому персонаж
        #    оказывается то перед объектом, то за ним, в зависимости от
        #    того, кто стоит «ближе к зрителю».
        if show_cone:
            player_renderer.draw_attack_cone(screen, camera_x, camera_y)

        y_sort_renderer.draw(
            screen, camera_x, camera_y,
            game_map=game_map, player=player, slimes=slimes, ranged=ranged,
        )

        # 3. Снаряды — летят поверх Y-сортированной сцены (в воздухе)
        ranged_renderer.draw_projectiles(ranged, screen, camera_x, camera_y)

        # Отладка: зелёный хитбокс
        if show_walls:
            hb = player.hitbox.move(-camera_x, -camera_y)
            pygame.draw.rect(screen, (0, 255, 0), hb, 2)
            wx = int(player.world_x) - camera_x
            wy = int(player.world_y) - camera_y
            pygame.draw.line(screen, (255, 255, 255), (wx - 6, wy), (wx + 6, wy), 1)
            pygame.draw.line(screen, (255, 255, 255), (wx, wy - 6), (wx, wy + 6), 1)

        hud.draw(screen, player)
        inv_panel.draw(screen, player.inventory)

        # Волна в HUD
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
                "F4=стены+хитбокс  F5=конус  Q=слаймы  E=дальний  TAB=инвентарь",
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

        # Перед новой игрой — показываем интро (ЭТАП 5.2)
        if result == "new_game":
            intro = IntroScreen(screen)
            intro.run()  # "done" или "skip" — в любом случае запускаем игру
            save = None
        else:
            save = result[len("load:"):] if result.startswith("load:") else None

        outcome = run_game(save_path=save)

        if outcome == "quit":
            break

    pygame.quit()


if __name__ == "__main__":
    main()