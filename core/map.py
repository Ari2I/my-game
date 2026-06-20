"""
core/map.py — модель тайловой карты (TileMap) + утилита get_content_bounds.

Добавление для Y-сортировки (depth sorting):
  TileMap различает два рода слоёв:
    - GROUND_LAYER_NAMES   — «земля»: всегда рисуется под игроком/врагами.
    - OBJECT_LAYER_NAMES   — «высокие» объекты (деревья, постройки, мосты):
      их тайлы участвуют в Y-сортировке вместе с игроком и врагами,
      чтобы персонаж мог оказаться то перед объектом, то за ним.

  draw_ground()   — рисует только слои земли (вызывать первым).
  iter_object_sprites() — отдаёт «высокие» тайлы как список (y_sort, draw_fn),
                          не рисуя их сразу — для последующей сортировки
                          вместе с игроком/врагами в main.py.
"""

import pygame
import pytmx

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


class TileMap:

    def __init__(self, filename):
        self.filename = filename
        self.tmx_data = pytmx.load_pygame(filename)
        self.tile_scale = 4  # Масштаб увеличения тайлов (в 4 раза)
        self.tile_width = 16 * self.tile_scale  # 64 пикселя
        self.tile_height = 16 * self.tile_scale  # 64 пикселя

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

    # ── «высокие» тайлы — для Y-сортировки вместе с игроком/врагами ──────────
    def iter_object_sprites(self, layer_names: set[str] | None = None):
        """
        Возвращает список кортежей (y_sort_key, tile_image, world_x, world_y)
        для тайлов из «объектных» слоёв (деревья, постройки, мосты).

        y_sort_key — Y-координата нижнего края тайла в мировых пикселях;
        используется для сортировки вместе с игроком и врагами в main.py.

        tile_image — уже МАСШТАБИРОВАННЫЙ Surface (контракт единый с
        CachedTileMap.iter_object_sprites(), которая кэширует именно
        отмасштабированные тайлы) — готов к прямому screen.blit().

        Не рисует ничего сам — только собирает данные.
        """
        names = layer_names if layer_names is not None else OBJECT_LAYER_NAMES
        sprites = []
        for layer in self._iter_tile_layers(self.tmx_data.visible_layers):
            if layer.name not in names:
                continue
            for x, y, gid in layer:
                tile = self.tmx_data.get_tile_image_by_gid(gid)
                if not tile:
                    continue
                scaled = pygame.transform.scale(
                    tile, (self.tile_width, self.tile_height))
                world_x = x * self.tile_width
                world_y = y * self.tile_height
                y_sort_key = world_y + self.tile_height  # нижний край тайла
                sprites.append((y_sort_key, scaled, world_x, world_y))
        return sprites
