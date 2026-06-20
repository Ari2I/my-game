"""
core/map.py — модель тайловой карты (TileMap) + утилита get_content_bounds.

Y-сортировка (depth sorting) и проблема крупных объектов
──────────────────────────────────────────────────────────────────────────────
TileMap различает два рода слоёв:
  - GROUND_LAYER_NAMES — «земля»: всегда рисуется под игроком/врагами.
  - OBJECT_LAYER_NAMES — «высокие» объекты (деревья, постройки, мосты,
    крупные декорации вроде многотайловых боссов/монументов): их тайлы
    участвуют в Y-сортировке вместе с игроком и врагами, чтобы персонаж
    мог оказаться то перед объектом, то за ним.

ВАЖНО (исправление): объектный слой в Tiled часто содержит не только мелкие
одно-двухтайловые объекты, но и КРУПНЫЕ многотайловые декорации (например,
монумент/босс размером 6×8 тайлов). Если сортировать ПОТАЙЛОВО — присваивая
каждому отдельному тайлу свой собственный y_sort_key (низ именно этого
тайла) — крупный объект «разваливается»: верхние тайлы объекта получают
маленький Y и оказываются «дальше» игрока, нижние — «ближе», и при сравнении
с ОДНИМ Y игрока часть объекта рисуется перед ним, а часть — за, разрезая
персонажа пополам (видна только нижняя часть/хитбокс, верх и торс «тонут»
под объектом).

Решение: тайлы одного объектного слоя группируются в СВЯЗНЫЕ блоки (flood
fill по 4-связности — общая сторона по сетке) внутри каждого слоя отдельно.
Вся группа получает ОДИН y_sort_key — Y нижнего края самого нижнего тайла
группы («точка опоры» объекта на земле), и рисуется/сортируется как единое
целое. Мелкие объекты (1-2 тайла) превращаются в группы из 1-2 элементов и
ведут себя как раньше — регрессии для них нет. Группировка считается ОДИН
РАЗ при загрузке карты и кэшируется (TileMap) — на 60 FPS пересчитывать
компоненты связности каждый кадр было бы расточительно.

  draw_ground()         — рисует только слои земли (вызывать первым).
  iter_object_sprites()  — отдаёт список ГРУПП тайлов:
                           [(y_sort_key, [(tile_image, world_x, world_y), ...]), ...]
                           Не рисует ничего сама — только собирает данные для
                           последующей сортировки вместе с игроком/врагами
                           в core/render/y_sort_renderer.py.
"""

import pygame
import pytmx
from collections import deque

# ─── Слои земли — всегда под игроком, без Y-сортировки ───────────────────────
# ВАЖНО: имена должны ТОЧНО совпадать с именами layer'ов в твоём .tmx файле
# (открой карту в Tiled и проверь панель Layers, если меняешь набор тайлсетов).
#
# Для mapV1.tmx (на момент написания) фактические слои такие:
#   water         (id=1)  — вода и берега            -> ЗЕМЛЯ
#   flor          (id=6)  — основной пол/грунт        -> ЗЕМЛЯ
#   ground_3      (id=7)  — дополнительный слой земли -> ЗЕМЛЯ
#   ground_2      (id=8)  — дополнительный слой земли -> ЗЕМЛЯ
#   Tile Layer 5  (id=9)  — декор/мелкие объекты      -> ОБЪЕКТЫ (Y-сортировка)
#   4             (id=10) — постройки/крупные объекты -> ОБЪЕКТЫ (Y-сортировка)
#   Tile Layer 7  (id=11) — стены/высокие объекты     -> ОБЪЕКТЫ (Y-сортировка)
#   Tile Layer 8  (id=12) — верхний декор/кроны       -> ОБЪЕКТЫ (Y-сортировка)
#
# Если у тебя другие имена слоёв (например, после правок в Tiled) —
# поправь множества ниже. Слой, который должен «закрывать» персонажа снизу
# (стены, стволы деревьев, заборы) — в OBJECT_LAYER_NAMES.
# Слой, который персонаж всегда топчет (трава, дорожки, вода) — в GROUND_LAYER_NAMES.
GROUND_LAYER_NAMES: set[str] = {
    "water",
    "flor",
    "Tile Layer 7",
}

# ─── Слои «высоких» объектов — участвуют в Y-сортировке с игроком/врагами ────
OBJECT_LAYER_NAMES: set[str] = {
    "Tile Layer 5",
    "Tile Layer 8",
    "4",
    "ground_2",
    "ground_3",
}


def get_content_bounds(tmx_data, tile_w, tile_h):
    """
    Возвращает (x0, y0, x1, y1) в пикселях — реальные границы непустого
    содержимого карты (без учёта полностью пустых краёв тайлового грида).

    Если карта полностью пуста — возвращает границы по номинальному размеру.
    """

    def iter_layers(layers):
        for layer in layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                yield layer
            elif hasattr(layer, "layers"):
                yield from iter_layers(layer.layers)

    min_x = min_y = max_x = max_y = None
    for layer in iter_layers(tmx_data.visible_layers):
        for x, y, gid in layer:
            if gid == 0:
                continue
            if min_x is None or x < min_x: min_x = x
            if max_x is None or x > max_x: max_x = x
            if min_y is None or y < min_y: min_y = y
            if max_y is None or y > max_y: max_y = y

    if min_x is None:
        return 0, 0, tmx_data.width * tile_w, tmx_data.height * tile_h

    return (min_x * tile_w, min_y * tile_h,
            (max_x + 1) * tile_w, (max_y + 1) * tile_h)


def _group_cells_by_connectivity(cells: dict[tuple[int, int], int]
                                 ) -> list[list[tuple[int, int, int]]]:
    """
    Группирует занятые ячейки одного слоя в связные компоненты (flood fill,
    4-связность: общая сторона по сетке — вверх/вниз/влево/вправо).

    Args:
        cells: словарь {(tile_x, tile_y): gid} — все непустые ячейки слоя.

    Returns:
        Список групп; каждая группа — список (tile_x, tile_y, gid).

    Зачем нужна 4-связность, а не 8 (с диагоналями): диагональное касание
    двух тайлов в Tiled обычно не означает, что это визуально один объект
    (в отличие от смежности по стороне, которая почти всегда означает
    непрерывный силуэт). 4-связность даёт более точную и предсказуемую
    группировку для типичных тайловых декораций.
    """
    visited: set[tuple[int, int]] = set()
    groups: list[list[tuple[int, int, int]]] = []

    for start in cells:
        if start in visited:
            continue

        # BFS от стартовой ячейки — собираем всю связную компоненту
        queue = deque([start])
        visited.add(start)
        group: list[tuple[int, int, int]] = []

        while queue:
            cx, cy = queue.popleft()
            group.append((cx, cy, cells[(cx, cy)]))

            for nx, ny in ((cx + 1, cy), (cx - 1, cy),
                          (cx, cy + 1), (cx, cy - 1)):
                if (nx, ny) in cells and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))

        groups.append(group)

    return groups


class TileMap:

    def __init__(self, filename):
        self.filename = filename
        self.tmx_data = pytmx.load_pygame(filename)
        self.tile_scale = 4  # Масштаб увеличения тайлов (в 4 раза)
        self.tile_width = 16 * self.tile_scale  # 64 пикселя
        self.tile_height = 16 * self.tile_scale  # 64 пикселя

        # Кэш группировки объектных слоёв (см. _group_cells_by_connectivity).
        # Ключ — frozenset имён слоёв, чтобы поддержать вызов с произвольным
        # layer_names без пересчёта при повторном использовании набора по
        # умолчанию. Считается лениво, при первом обращении.
        self._object_groups_cache: dict[frozenset, list] = {}

    def _iter_tile_layers(self, layers):
        for layer in layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                yield layer
            elif hasattr(layer, "layers"):
                yield from self._iter_tile_layers(layer.layers)

    # ── обычная отрисовка всех слоёв подряд (без Y-сортировки) ───────────────
    def draw(self, screen, camera_x=0, camera_y=0):
        """Рисует ВСЕ слои карты одним проходом (старое поведение)."""
        for layer in self._iter_tile_layers(self.tmx_data.visible_layers):
            for x, y, gid in layer:
                tile = self.tmx_data.get_tile_image_by_gid(gid)
                if tile:
                    scaled_tile = pygame.transform.scale(
                        tile, (self.tile_width, self.tile_height))
                    screen.blit(scaled_tile,
                                (x * self.tile_width - camera_x,
                                 y * self.tile_height - camera_y))

    # ── только «земля» — рисуется под игроком/врагами ────────────────────────
    def draw_ground(self, screen, camera_x=0, camera_y=0,
                    layer_names: set[str] | None = None):
        """
        Рисует только слои земли (GROUND_LAYER_NAMES по умолчанию).
        Вызывать ПЕРВЫМ, до отрисовки игрока/врагов/Y-сортируемых объектов.
        """
        names = layer_names if layer_names is not None else GROUND_LAYER_NAMES
        for layer in self._iter_tile_layers(self.tmx_data.visible_layers):
            if layer.name not in names:
                continue
            for x, y, gid in layer:
                tile = self.tmx_data.get_tile_image_by_gid(gid)
                if tile:
                    scaled_tile = pygame.transform.scale(
                        tile, (self.tile_width, self.tile_height))
                    screen.blit(scaled_tile,
                                (x * self.tile_width - camera_x,
                                 y * self.tile_height - camera_y))

    # ── построение связных групп тайлов объектных слоёв (с кэшем) ────────────
    def _get_object_groups(self, layer_names: set[str]
                           ) -> list[tuple[int, int, list[tuple[int, int, int]]]]:
        """
        Возвращает закэшированный список (layer_index, gid_placeholder,
        group) — на деле список троек, где каждая тройка описывает одну
        связную группу тайлов ОДНОГО объектного слоя:
            (min_y_sort_key_unused, layer_marker, group_cells)

        Реализация хранит группы как просто list[group_cells] на слой;
        см. _build_object_groups для точного формата.
        """
        key = frozenset(layer_names)
        if key not in self._object_groups_cache:
            self._object_groups_cache[key] = self._build_object_groups(layer_names)
        return self._object_groups_cache[key]

    def _build_object_groups(self, layer_names: set[str]):
        """
        Строит связные группы тайлов для каждого объектного слоя отдельно
        (группировка НЕ смешивает тайлы разных слоёв — у каждого слоя своя
        смысловая роль в декоре карты).

        Returns:
            Список словарей {"layer": layer_name, "cells": [(tx, ty, gid), ...]}
            — одна запись на одну связную группу.
        """
        all_groups = []
        for layer in self._iter_tile_layers(self.tmx_data.visible_layers):
            if layer.name not in layer_names:
                continue

            cells: dict[tuple[int, int], int] = {}
            for x, y, gid in layer:
                if gid == 0:
                    continue
                cells[(x, y)] = gid

            if not cells:
                continue

            for group_cells in _group_cells_by_connectivity(cells):
                all_groups.append({"layer": layer.name, "cells": group_cells})

        return all_groups

    # ── «высокие» тайлы — для Y-сортировки вместе с игроком/врагами ──────────
    def iter_object_sprites(self, layer_names: set[str] | None = None):
        """
        Возвращает список ГРУПП тайлов из «объектных» слоёв (деревья,
        постройки, мосты, крупные декорации):

            [(y_sort_key, [(tile_image, world_x, world_y), ...]), ...]

        y_sort_key — Y-координата нижнего края САМОГО НИЖНЕГО тайла группы
        («точка опоры» всего объекта на земле). Все тайлы одной связной
        группы (см. docstring модуля) делят один и тот же y_sort_key и
        рисуются вместе как единое целое — это и есть исправление проблемы
        «разваливания» крупных многотайловых объектов при Y-сортировке.

        tile_image — уже МАСШТАБИРОВАННЫЙ Surface (контракт единый с
        CachedTileMap.iter_object_sprites(), которая кэширует именно
        отмасштабированные тайлы) — готов к прямому screen.blit().

        Не рисует ничего сам — только собирает данные.
        """
        names = layer_names if layer_names is not None else OBJECT_LAYER_NAMES
        groups = self._get_object_groups(names)

        result = []
        for group in groups:
            tiles_out = []
            max_bottom = None
            for tx, ty, gid in group["cells"]:
                tile = self.tmx_data.get_tile_image_by_gid(gid)
                if not tile:
                    continue
                scaled = pygame.transform.scale(
                    tile, (self.tile_width, self.tile_height))
                world_x = tx * self.tile_width
                world_y = ty * self.tile_height
                tile_bottom = world_y + self.tile_height
                if max_bottom is None or tile_bottom > max_bottom:
                    max_bottom = tile_bottom
                tiles_out.append((scaled, world_x, world_y))

            if tiles_out:
                result.append((float(max_bottom), tiles_out))

        return result