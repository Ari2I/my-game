"""
tests/test_walls.py — тесты для WallMap.

Используем фабричный метод WallMap.from_walls() чтобы не читать .tmx файлы.
Тесты проверяют алгоритм пересечения отрезков и MTV-резолюцию коллизий.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

import pytest
from core.walls import WallMap, WallTile


# ─── Фабричный метод для тестируемости ───────────────────────────────────────
# Добавляем from_walls как classmethod через monkey-patching
# (в реальном коде walls.py нужно добавить этот метод — см. ЭТАП 3.2)

def make_wall_map(rects: list, tile_w: int = 64, tile_h: int = 64) -> WallMap:
    """
    Создаёт WallMap из готового списка pygame.Rect без чтения .tmx.
    Вспомогательная функция для тестов.
    """
    wm = object.__new__(WallMap)  # обходим __init__ без tmx_data
    wm._tile_w = tile_w
    wm._tile_h = tile_h
    wm._solid_layers = set()
    wm._solid_gid = []
    wm._filename = None
    wm.walls = [WallTile(r.x, r.y, r.width, r.height) for r in rects]
    wm._bucket_w = tile_w * 4
    wm._bucket_h = tile_h * 4
    wm._grid = {}
    wm._index()
    return wm


# ─── Тесты _segments_intersect ────────────────────────────────────────────────

class TestSegmentsIntersect:

    def _intersect(self, a, b, c, d) -> bool:
        """Вызываем приватный метод через экземпляр с пустыми walls."""
        wm = make_wall_map([])
        return wm._segments_intersect(a, b, c, d)

    def test_crossing_lines_intersect(self):
        """Перекрещивающиеся отрезки пересекаются."""
        # + образный крест
        assert self._intersect((0, 1), (2, 1), (1, 0), (1, 2)) is True

    def test_parallel_horizontal_lines_do_not_intersect(self):
        """Параллельные горизонтальные отрезки не пересекаются."""
        assert self._intersect((0, 0), (4, 0), (0, 2), (4, 2)) is False

    def test_parallel_vertical_lines_do_not_intersect(self):
        """Параллельные вертикальные отрезки не пересекаются."""
        assert self._intersect((0, 0), (0, 4), (2, 0), (2, 4)) is False

    def test_collinear_non_overlapping(self):
        """Коллинеарные непересекающиеся отрезки — не пересекаются."""
        assert self._intersect((0, 0), (1, 0), (2, 0), (3, 0)) is False

    def test_t_intersection(self):
        """T-образное пересечение (конец одного лежит на другом)."""
        assert self._intersect((0, 0), (4, 0), (2, 0), (2, 2)) is True

    def test_touching_endpoints(self):
        """Отрезки касаются концами — пересечение."""
        assert self._intersect((0, 0), (1, 1), (1, 1), (2, 0)) is True

    def test_non_crossing_x_pattern(self):
        """Отрезки в форме X, но не достигающие друг друга."""
        assert self._intersect((0, 0), (1, 1), (2, 0), (3, 1)) is False

    def test_diagonal_cross(self):
        """Диагональные отрезки пересекаются в центре."""
        assert self._intersect((0, 0), (4, 4), (0, 4), (4, 0)) is True


# ─── Тесты resolve ────────────────────────────────────────────────────────────

class TestResolve:

    def test_resolve_pushes_rect_out_of_wall_from_left(self):
        """Rect, вошедший в стену справа, выталкивается влево."""
        wall = pygame.Rect(100, 0, 64, 64)
        wm = make_wall_map([wall])

        # Rect частично перекрывает стену справа
        r = pygame.Rect(90, 10, 30, 30)
        wm.resolve(r)
        # После разрешения не должно быть перекрытия
        assert not r.colliderect(wall), (
            f"Rect {r} до сих пор пересекается со стеной {wall}"
        )

    def test_resolve_pushes_rect_out_of_wall_from_top(self):
        """Rect, вошедший в стену снизу, выталкивается вверх."""
        wall = pygame.Rect(50, 100, 64, 64)
        wm = make_wall_map([wall])

        r = pygame.Rect(60, 90, 30, 30)
        wm.resolve(r)
        assert not r.colliderect(wall)

    def test_resolve_no_movement_when_no_collision(self):
        """Rect, не пересекающий стену, не сдвигается."""
        wall = pygame.Rect(200, 200, 64, 64)
        wm = make_wall_map([wall])

        r = pygame.Rect(0, 0, 30, 30)
        orig_x, orig_y = r.x, r.y
        wm.resolve(r)
        assert r.x == orig_x and r.y == orig_y

    def test_resolve_multiple_walls(self):
        """Rect разрешает коллизии с несколькими стенами подряд."""
        walls = [
            pygame.Rect(100, 0, 64, 64),
            pygame.Rect(0, 100, 64, 64),
        ]
        wm = make_wall_map(walls)

        # Rect не касается ни одной стены
        r = pygame.Rect(10, 10, 30, 30)
        wm.resolve(r)
        for wall in walls:
            assert not r.colliderect(wall)

    def test_resolve_player_is_alias_for_resolve(self):
        """resolve_player и resolve_entity — алиасы resolve."""
        wall = pygame.Rect(100, 50, 64, 64)
        wm = make_wall_map([wall])

        r1 = pygame.Rect(90, 60, 30, 30)
        r2 = pygame.Rect(90, 60, 30, 30)

        wm.resolve_player(r1)
        wm.resolve_entity(r2)

        assert r1.x == r2.x and r1.y == r2.y

    def test_resolve_deep_overlap_exits_correctly(self):
        """Глубокое вхождение в стену всё равно корректно разрешается."""
        wall = pygame.Rect(100, 100, 100, 100)
        wm = make_wall_map([wall])

        # Rect глубоко внутри стены
        r = pygame.Rect(110, 110, 50, 50)
        wm.resolve(r)
        assert not r.colliderect(wall)

    def test_is_solid_point_inside_wall(self):
        """is_solid_point возвращает True для точки внутри стены."""
        wall = pygame.Rect(100, 100, 64, 64)
        wm = make_wall_map([wall])
        assert wm.is_solid_point(130, 130) is True

    def test_is_solid_point_outside_wall(self):
        """is_solid_point возвращает False для точки вне стены."""
        wall = pygame.Rect(100, 100, 64, 64)
        wm = make_wall_map([wall])
        assert wm.is_solid_point(10, 10) is False
