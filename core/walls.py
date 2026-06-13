"""
core/walls.py — заготовка системы стен.

Концепция:
  WallMap читает слои карты Tiled (.tmx) и собирает коллизионные rect-ы
  для тайлов, помеченных как «solid». В Tiled нужно добавить булевое
  свойство  solid = true  у нужных тайлов (через Tileset → Tile Properties).

  Если свойство ещё не проставлено — в качестве fallback можно
  явно указать список GID или имён слоёв.

Публичный API:
  wall_map = WallMap(tmx_data, tile_w, tile_h)
  wall_map.resolve_player(player.rect)       → сдвигает rect игрока
  wall_map.resolve_entity(rect)              → то же для любого rect-а
  wall_map.debug_draw(screen, camera_x, camera_y)  → красные рамки (debug)

Алгоритм разрешения коллизий:
  Minimum Translation Vector (MTV) по обеим осям отдельно,
  с приоритетом оси с меньшим перекрытием.
"""

import pygame
import pytmx
from typing import Optional


# ─── Слои, считающиеся «непроходимыми» по умолчанию ──────────────────────────
# Добавь сюда имена слоёв из своего .tmx, которые должны блокировать движение.
SOLID_LAYER_NAMES: set[str] = {
    "elevated_space",
    "elevated_space2",
    "elevated_space3",
    "elevated_space_corners",
    "bridges",      # мосты — проходимы поверх воды, но блокируют сбоку
}

# GID-диапазоны тайлсетов, которые всегда solid
# (заполнишь когда определишь конкретные тайлы)
SOLID_GID_RANGES: list[tuple[int, int]] = [
    # (first_gid, last_gid),
    # пример: (10714, 11675),   # Bridges
]


class WallTile:
    """Один непроходимый тайл с мировым rect-ом."""
    __slots__ = ("rect",)

    def __init__(self, x: int, y: int, w: int, h: int):
        self.rect = pygame.Rect(x, y, w, h)


class WallMap:
    def __init__(self, tmx_data: pytmx.TiledMap,
                 tile_w: int, tile_h: int,
                 solid_layers: Optional[set[str]] = None,
                 solid_gid_ranges: Optional[list[tuple[int, int]]] = None):

        self._tile_w = tile_w
        self._tile_h = tile_h
        self._solid_layers = solid_layers if solid_layers is not None else SOLID_LAYER_NAMES
        self._solid_gid    = solid_gid_ranges if solid_gid_ranges is not None else SOLID_GID_RANGES

        self.walls: list[WallTile] = []
        self._build(tmx_data)

        # Пространственный хэш для быстрого поиска (bucket = tile_w*4 × tile_h*4)
        self._bucket_w = tile_w * 4
        self._bucket_h = tile_h * 4
        self._grid: dict[tuple[int, int], list[WallTile]] = {}
        self._index()

    # ── построение ────────────────────────────────────────────────────────────
    def _is_solid_gid(self, gid: int) -> bool:
        for lo, hi in self._solid_gid:
            if lo <= gid <= hi:
                return True
        return False

    def _build(self, tmx: pytmx.TiledMap):
        tw, th = self._tile_w, self._tile_h
        for layer in tmx.visible_layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue

            layer_solid = layer.name in self._solid_layers

            for tx, ty, gid in layer:
                if gid == 0:
                    continue
                # Проверяем: (1) имя слоя, (2) GID-диапазон, (3) свойство solid
                tile_solid = layer_solid or self._is_solid_gid(gid)

                if not tile_solid:
                    # пробуем Tiled-свойство тайла
                    try:
                        props = tmx.get_tile_properties_by_gid(gid)
                        if props and props.get("solid", False):
                            tile_solid = True
                    except Exception:
                        pass

                if tile_solid:
                    self.walls.append(WallTile(tx * tw, ty * th, tw, th))

        print(f"[WallMap] Построено {len(self.walls)} коллизионных тайлов.")

    # ── пространственный индекс ────────────────────────────────────────────────
    def _bucket(self, x: int, y: int) -> tuple[int, int]:
        return (x // self._bucket_w, y // self._bucket_h)

    def _index(self):
        for w in self.walls:
            bx0, by0 = self._bucket(w.rect.left,  w.rect.top)
            bx1, by1 = self._bucket(w.rect.right, w.rect.bottom)
            for bx in range(bx0, bx1 + 1):
                for by in range(by0, by1 + 1):
                    self._grid.setdefault((bx, by), []).append(w)

    def _nearby(self, rect: pygame.Rect) -> list[WallTile]:
        bx0, by0 = self._bucket(rect.left,  rect.top)
        bx1, by1 = self._bucket(rect.right, rect.bottom)
        seen: set[int] = set()
        result: list[WallTile] = []
        for bx in range(bx0, bx1 + 1):
            for by in range(by0, by1 + 1):
                for w in self._grid.get((bx, by), []):
                    wid = id(w)
                    if wid not in seen:
                        seen.add(wid)
                        result.append(w)
        return result

    # ── разрешение коллизий (MTV по осям) ─────────────────────────────────────
    def resolve(self, rect: pygame.Rect) -> pygame.Rect:
        """
        Сдвигает rect, чтобы он не перекрывал стены.
        Возвращает исправленный rect (объект изменяется на месте).
        """
        for w in self._nearby(rect):
            if not rect.colliderect(w.rect):
                continue

            # Перекрытия по каждой оси
            over_x_left  = rect.right  - w.rect.left
            over_x_right = w.rect.right  - rect.left
            over_y_up    = rect.bottom - w.rect.top
            over_y_down  = w.rect.bottom - rect.top

            ox = over_x_left  if over_x_left  < over_x_right  else -over_x_right
            oy = over_y_up    if over_y_up     < over_y_down   else -over_y_down

            # Толкаем по оси с меньшим перекрытием
            if abs(ox) < abs(oy):
                rect.x -= ox
            else:
                rect.y -= oy

        return rect

    def resolve_player(self, player_rect: pygame.Rect) -> pygame.Rect:
        return self.resolve(player_rect)

    def resolve_entity(self, entity_rect: pygame.Rect) -> pygame.Rect:
        return self.resolve(entity_rect)

    # ── запрос: точка внутри стены? ───────────────────────────────────────────
    def is_solid_point(self, x: float, y: float) -> bool:
        probe = pygame.Rect(int(x) - 1, int(y) - 1, 2, 2)
        return any(probe.colliderect(w.rect) for w in self._nearby(probe))

    # ── отладочная отрисовка ──────────────────────────────────────────────────
    def debug_draw(self, screen: pygame.Surface,
                   camera_x: int = 0, camera_y: int = 0):
        sw, sh = screen.get_size()
        for w in self.walls:
            rx = w.rect.x - camera_x
            ry = w.rect.y - camera_y
            if rx > sw or ry > sh or rx + w.rect.w < 0 or ry + w.rect.h < 0:
                continue
            pygame.draw.rect(screen, (220, 50, 50),
                             (rx, ry, w.rect.w, w.rect.h), 1)