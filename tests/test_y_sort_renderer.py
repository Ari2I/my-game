"""
tests/test_y_sort_renderer.py — тесты Y-сортировки (depth sorting).

Проверяем, что YSortRenderer строит порядок отрисовки строго по возрастанию
Y-координаты нижней точки сущности: объект с меньшим Y (выше на экране,
«дальше») рисуется раньше объекта с большим Y («ближе», перекрывает).

Тесты не проверяют визуальный пиксельный результат (это сделал бы интеграционный
тест с реальным экраном), а проверяют сам алгоритм построения порядка через
перехват вызовов отрисовки (порядок side-эффектов).

Точка сортировки игрока — body_rect.bottom (нижняя точка ПОЛНОГО визуального
силуэта спрайта), а не hitbox.bottom (узкий хитбокс у ног, нужен только для
коллизий со стенами карты). См. докстринг core/render/y_sort_renderer.py и
core/player.py — почему это разделение важно для корректного перекрытия
объектами карты.

ВАЖНО про контракт game_map.iter_object_sprites():
    Реальный core/map.py (и main.py::CachedTileMap) отдают список ГРУПП:
        [(y_sort_key, [(tile_image, world_x, world_y), ...]), ...]
    то есть каждый элемент — кортеж из ДВУХ значений: y_sort_key и список
    тайлов этой связной группы (см. core/map.py:_build_object_groups —
    группировка через BFS по 4-связности, чтобы крупные многотайловые
    объекты не «разваливались» при сортировке). make_game_map() ниже
    собирает мок именно в этом формате — каждая переданная «плоская»
    запись (y_sort_key, surf, x, y) оборачивается в группу из ОДНОГО
    тайла: (y_sort_key, [(surf, x, y)]). Для целей этих тестов (порядок
    сортировки одиночных объектов) одно-тайловая группа эквивалентна
    отдельному объекту, но соответствует реальному контракту, который
    использует YSortRenderer.draw() (см. core/render/y_sort_renderer.py:
    `for y_sort_key, tile_group in game_map.iter_object_sprites()`).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

import pytest
import unittest.mock as mock

from core.render.y_sort_renderer import YSortRenderer
from core.slime import SlimeManager
from core.ranged_enemy import RangedEnemyManager

SCREEN = pygame.Surface((800, 600))


class _TrackingScreen:
    """
    Лёгкая обёртка вокруг pygame.Surface для перехвата вызовов blit().

    pygame.Surface.blit — встроенный C-метод, который нельзя пропатчить
    через unittest.mock.patch.object (атрибут read-only). Вместо патчинга
    передаём YSortRenderer объект-обёртку с собственным blit(), который
    делегирует реальной поверхности и параллельно фиксирует порядок вызовов.
    """

    def __init__(self, real_surface: pygame.Surface):
        self._real = real_surface
        self.blit_calls: list = []

    def blit(self, surface, dest, *args, **kwargs):
        self.blit_calls.append(surface)
        return self._real.blit(surface, dest, *args, **kwargs)

    def __getattr__(self, name):
        # Делегируем все остальные обращения (get_size, fill, и т.д.) реальному Surface
        return getattr(self._real, name)


def make_player(bottom_y: float, body_bottom_y: float | None = None):
    """
    Mock игрока.

    bottom_y       — нижняя точка hitbox (ноги, для коллизий/боя — НЕ
                      используется этим рендерером, оставлен для полноты mock).
    body_bottom_y  — нижняя точка body_rect (полный силуэт спрайта).
                      Именно это значение используется YSortRenderer для
                      сортировки. Если не задан — берётся равным bottom_y
                      (для тестов, которым важна только сама механика
                      сортировки, а не конкретное расхождение хитбокса
                      и силуэта).
    """
    if body_bottom_y is None:
        body_bottom_y = bottom_y

    p = mock.MagicMock()
    p.hitbox = pygame.Rect(100, int(bottom_y) - 28, 28, 28)  # bottom == bottom_y
    p.is_attacking = False
    p.is_invincible = False
    p.image = pygame.Surface((32, 32))
    p.rect = pygame.Rect(90, int(body_bottom_y) - 32, 32, 32)
    # body_rect — отдельный публичный rect полного силуэта (см. core/player.py).
    # В реальном коде это property, возвращающее self.rect; в mock задаём
    # тем же прямоугольником, чтобы .bottom давал нужное тестовое значение.
    p.body_rect = p.rect
    return p


def make_game_map(object_sprites: list):
    """
    Mock карты, отдающей список «плоских» записей (y_sort_key, surf, x, y) —
    каждая запись описывает ОДИН тайл-объект.

    Реальный контракт core/map.py::iter_object_sprites() — список ГРУПП
    тайлов: [(y_sort_key, [(surf, x, y), ...]), ...] (см. докстринг модуля
    выше). Чтобы тесты могли оперировать простыми одиночными объектами, не
    теряя соответствия реальному контракту, каждая «плоская» запись здесь
    оборачивается в группу из одного элемента:

        (y_sort_key, surf, x, y)  ->  (y_sort_key, [(surf, x, y)])

    Так YSortRenderer.draw(), которая распаковывает
    `for y_sort_key, tile_group in game_map.iter_object_sprites()`,
    получает данные ровно в том формате, в котором их реально отдаёт
    CachedTileMap/TileMap в проде.
    """
    grouped = [
        (y_sort_key, [(surf, x, y)])
        for (y_sort_key, surf, x, y) in object_sprites
    ]
    gm = mock.MagicMock()
    gm.iter_object_sprites.return_value = grouped
    return gm


def make_renderers():
    """Создаёт PlayerRenderer/SlimeRenderer/RangedRenderer с фиксацией порядка вызовов draw_one/draw."""
    call_order = []

    player_renderer = mock.MagicMock()
    player_renderer.draw.side_effect = lambda *a, **k: call_order.append("player")
    player_renderer.draw_iframe_flash.side_effect = lambda *a, **k: None

    slime_renderer = mock.MagicMock()
    slime_renderer.draw_one.side_effect = lambda slime, *a, **k: call_order.append(("slime", slime))

    ranged_renderer = mock.MagicMock()
    ranged_renderer.draw_one.side_effect = lambda enemy, *a, **k: call_order.append(("ranged", enemy))

    return player_renderer, slime_renderer, ranged_renderer, call_order


class TestYSortOrdering:

    def test_object_above_player_drawn_before_player(self):
        """Объект с меньшим Y (выше на экране) рисуется ДО игрока — то есть «за» ним."""
        player = make_player(bottom_y=200)
        tile_surf = pygame.Surface((64, 64))
        # объект с y_sort_key=50 — значительно выше игрока (200)
        game_map = make_game_map([(50.0, tile_surf, 64, -14)])

        player_renderer, slime_renderer, ranged_renderer, call_order = make_renderers()
        slimes = SlimeManager(2000, 2000)
        ranged = RangedEnemyManager(2000, 2000)

        tracking_screen = _TrackingScreen(SCREEN)
        player_renderer.draw.side_effect = lambda *a, **k: call_order.append("player")

        y_sort = YSortRenderer(player_renderer, slime_renderer, ranged_renderer)
        y_sort.draw(tracking_screen, 0, 0, game_map=game_map,
                    player=player, slimes=slimes, ranged=ranged)

        # Тайл с y_sort_key=50 (< body_rect.bottom=200 игрока) обязан быть
        # отрисован раньше игрока в общем порядке вызовов.
        assert tile_surf in tracking_screen.blit_calls
        assert "player" in call_order

    def test_object_below_player_drawn_after_player(self):
        """Объект с большим Y (ниже на экране) рисуется ПОСЛЕ игрока — то есть «перед» ним."""
        player = make_player(bottom_y=100)
        tile_surf = pygame.Surface((64, 64))
        # объект с y_sort_key=300 — значительно ниже игрока (100)
        game_map = make_game_map([(300.0, tile_surf, 64, 236)])

        player_renderer, slime_renderer, ranged_renderer, call_order = make_renderers()
        slimes = SlimeManager(2000, 2000)
        ranged = RangedEnemyManager(2000, 2000)

        y_sort = YSortRenderer(player_renderer, slime_renderer, ranged_renderer)
        y_sort.draw(SCREEN, 0, 0, game_map=game_map,
                    player=player, slimes=slimes, ranged=ranged)

        assert "player" in call_order

    def test_full_ordering_is_sorted_by_y(self):
        """
        Комплексный тест: объект-ВЫШЕ, игрок, объект-НИЖЕ.
        Порядок отрисовки должен строго соответствовать возрастанию Y.
        """
        player = make_player(bottom_y=200)

        tile_above = pygame.Surface((64, 64))  # y_sort_key=50  < player(200)
        tile_below = pygame.Surface((64, 64))  # y_sort_key=350 > player(200)
        game_map = make_game_map([
            (350.0, tile_below, 64, 286),
            (50.0, tile_above, 64, -14),
        ])

        player_renderer, slime_renderer, ranged_renderer, call_order = make_renderers()
        slimes = SlimeManager(2000, 2000)
        ranged = RangedEnemyManager(2000, 2000)

        draw_sequence = []
        tracking_screen = _TrackingScreen(SCREEN)
        original_blit = tracking_screen.blit

        def tracking_blit(surface, dest, *a, **k):
            if surface is tile_above:
                draw_sequence.append("tile_above")
            elif surface is tile_below:
                draw_sequence.append("tile_below")
            return original_blit(surface, dest, *a, **k)

        tracking_screen.blit = tracking_blit

        player_renderer.draw.side_effect = lambda *a, **k: draw_sequence.append("player")

        y_sort = YSortRenderer(player_renderer, slime_renderer, ranged_renderer)
        y_sort.draw(tracking_screen, 0, 0, game_map=game_map,
                    player=player, slimes=slimes, ranged=ranged)

        assert draw_sequence == ["tile_above", "player", "tile_below"], (
            f"Неверный порядок Y-сортировки: {draw_sequence}"
        )

    def test_player_sorted_by_body_rect_not_hitbox(self):
        """
        Регрессионный тест на исправленный баг: сортировка должна идти по
        body_rect.bottom (полный силуэт), а НЕ по hitbox.bottom (ноги).

        Раньше хитбокс был смещён вниз и существенно меньше спрайта
        (HITBOX_OFFSET_Y, HITBOX_H в core/player.py), поэтому объект,
        чей y_sort_key оказывался между hitbox.bottom и верхней границей
        спрайта, перекрывал игрока некорректно («торчала голова»).

        Здесь намеренно разносим hitbox.bottom и body_rect.bottom на
        разные значения и проверяем, что в сортировке используется именно
        body_rect.bottom.
        """
        # hitbox «у ног» заканчивается на Y=400 (близко к земле),
        # но body_rect (полный спрайт) гораздо выше — заканчивается на Y=120.
        player = make_player(bottom_y=400, body_bottom_y=120)

        tile_surf = pygame.Surface((64, 64))
        # Объект с y_sort_key=200 — между hitbox.bottom(400) и body_rect.bottom(120).
        # Если бы сортировка ошибочно шла по hitbox.bottom (400), игрок
        # считался бы «ближе» этого объекта (400 > 200) и рисовался бы
        # ПОСЛЕ тайла — корректно. Но если сортировка идёт по
        # body_rect.bottom (120), игрок «дальше» объекта (120 < 200) и
        # должен рисоваться ДО тайла.
        game_map = make_game_map([(200.0, tile_surf, 64, 136)])

        player_renderer, slime_renderer, ranged_renderer, call_order = make_renderers()
        slimes = SlimeManager(2000, 2000)
        ranged = RangedEnemyManager(2000, 2000)

        draw_sequence = []
        tracking_screen = _TrackingScreen(SCREEN)
        original_blit = tracking_screen.blit

        def tracking_blit(surface, dest, *a, **k):
            if surface is tile_surf:
                draw_sequence.append("tile")
            return original_blit(surface, dest, *a, **k)

        tracking_screen.blit = tracking_blit
        player_renderer.draw.side_effect = lambda *a, **k: draw_sequence.append("player")

        y_sort = YSortRenderer(player_renderer, slime_renderer, ranged_renderer)
        y_sort.draw(tracking_screen, 0, 0, game_map=game_map,
                    player=player, slimes=slimes, ranged=ranged)

        assert draw_sequence == ["player", "tile"], (
            f"Сортировка должна идти по body_rect.bottom (120), а не "
            f"hitbox.bottom (400). Получен порядок: {draw_sequence}"
        )

    def test_slimes_and_ranged_enemies_participate_in_sorting(self):
        """Слаймы и дальние враги попадают в общий список сортировки по rect.bottom."""
        player = make_player(bottom_y=500)
        game_map = make_game_map([])

        player_renderer, slime_renderer, ranged_renderer, call_order = make_renderers()

        slimes = SlimeManager(2000, 2000)
        slimes.spawn_one(wave=1)
        slime_obj = slimes.enemies[0]
        slime_obj.rect.bottom = 100  # выше игрока

        ranged = RangedEnemyManager(2000, 2000)
        ranged.spawn_one(wave=1)
        ranged_obj = ranged.enemies[0]
        ranged_obj.rect.bottom = 900  # ниже игрока

        y_sort = YSortRenderer(player_renderer, slime_renderer, ranged_renderer)
        y_sort.draw(SCREEN, 0, 0, game_map=game_map,
                    player=player, slimes=slimes, ranged=ranged)

        # Извлекаем только относящиеся к сущностям записи (player/slime/ranged)
        entity_order = [c if isinstance(c, str) else c[0] for c in call_order]
        assert entity_order == ["slime", "player", "ranged"], (
            f"Неверный порядок: {entity_order}"
        )

    def test_empty_scene_does_not_crash(self):
        """Пустая сцена (нет тайлов-объектов, нет врагов) рисуется без ошибок."""
        player = make_player(bottom_y=100)
        game_map = make_game_map([])

        player_renderer, slime_renderer, ranged_renderer, call_order = make_renderers()
        slimes = SlimeManager(2000, 2000)
        ranged = RangedEnemyManager(2000, 2000)

        y_sort = YSortRenderer(player_renderer, slime_renderer, ranged_renderer)
        y_sort.draw(SCREEN, 0, 0, game_map=game_map,
                    player=player, slimes=slimes, ranged=ranged)

        assert call_order == ["player"]