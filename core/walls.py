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
import xml.etree.ElementTree as ET
from typing import Optional

# ─── Слои, считающиеся «непроходимыми» по умолчанию ──────────────────────────
# Добавь сюда имена слоёв из своего .tmx, которые должны блокировать движение.
SOLID_LAYER_NAMES: set[str] = {
    "elevated_space",
    "elevated_space2",
    "elevated_space3",
    "elevated_space_corners",
    "bridges",  # мосты — проходимы поверх воды, но блокируют сбоку
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


class WallPolygon:
    __slots__ = ("points", "rect", "closed")

    def __init__(self, points: list[tuple[int, int]], closed: bool = True):
        self.points = points
        self.closed = closed
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        left, top = min(xs), min(ys)
        right, bottom = max(xs), max(ys)
        self.rect = pygame.Rect(left, top, max(1, right - left), max(1, bottom - top))


class WallMap:
    def __init__(self, tmx_data: pytmx.TiledMap,
                 tile_w: int, tile_h: int,
                 solid_layers: Optional[set[str]] = None,
                 solid_gid_ranges: Optional[list[tuple[int, int]]] = None,
                 filename: Optional[str] = None):

        self._tile_w = tile_w
        self._tile_h = tile_h
        self._solid_layers = solid_layers if solid_layers is not None else SOLID_LAYER_NAMES
        self._solid_gid = solid_gid_ranges if solid_gid_ranges is not None else SOLID_GID_RANGES
        self._filename = filename

        self.walls: list[WallTile | WallPolygon] = []
        self._build(tmx_data)
        self._build_object_collisions(tmx_data)
        print(f"[WallMap] Построено {len(self.walls)} коллизионных объектов.")

        # Пространственный хэш для быстрого поиска (bucket = tile_w*4 × tile_h*4)
        self._bucket_w = tile_w * 4
        self._bucket_h = tile_h * 4
        self._grid: dict[tuple[int, int], list[WallTile | WallPolygon]] = {}
        self._index()

    # ── построение ────────────────────────────────────────────────────────────
    def _is_solid_gid(self, gid: int) -> bool:
        for lo, hi in self._solid_gid:
            if lo <= gid <= hi:
                return True
        return False

    def _iter_tile_layers(self, layers):
        for layer in layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                yield layer
            elif hasattr(layer, "layers"):
                yield from self._iter_tile_layers(layer.layers)

    def _build(self, tmx: pytmx.TiledMap):
        tw, th = self._tile_w, self._tile_h
        for layer in self._iter_tile_layers(tmx.visible_layers):
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

    def _build_object_collisions(self, tmx: pytmx.TiledMap):
        filename = self._filename or getattr(tmx, "filename", None)
        if not filename:
            return

        scale_x = self._tile_w / getattr(tmx, "tilewidth", 16)
        scale_y = self._tile_h / getattr(tmx, "tileheight", 16)

        try:
            root = ET.parse(filename).getroot()
        except Exception as exc:
            print(f"[WallMap] Could not read collision object layer: {exc}")
            return

        for group in root.findall("objectgroup"):
            group_name = group.attrib.get("name", "").lower()
            if group_name not in {"collision", "collisions", "walls", "wall"}:
                continue

            for obj in group.findall("object"):
                ox = float(obj.attrib.get("x", 0.0))
                oy = float(obj.attrib.get("y", 0.0))
                polygon = obj.find("polygon")
                polyline = obj.find("polyline")
                node = polygon if polygon is not None else polyline

                if node is not None:
                    points = self._parse_points(
                        node.attrib.get("points", ""), ox, oy, scale_x, scale_y
                    )
                    if len(points) >= 2:
                        self.walls.append(WallPolygon(points, closed=polygon is not None))
                    continue

                width = float(obj.attrib.get("width", 0.0))
                height = float(obj.attrib.get("height", 0.0))
                if width > 0 and height > 0:
                    self.walls.append(WallTile(
                        int(round(ox * scale_x)),
                        int(round(oy * scale_y)),
                        int(round(width * scale_x)),
                        int(round(height * scale_y)),
                    ))

    def _parse_points(self, raw: str, ox: float, oy: float,
                      scale_x: float, scale_y: float) -> list[tuple[int, int]]:
        points: list[tuple[int, int]] = []
        for token in raw.split():
            try:
                px, py = token.split(",", 1)
                points.append((
                    int(round((ox + float(px)) * scale_x)),
                    int(round((oy + float(py)) * scale_y)),
                ))
            except ValueError:
                continue
        return points

    # ── пространственный индекс ────────────────────────────────────────────────
    def _bucket(self, x: int, y: int) -> tuple[int, int]:
        return (x // self._bucket_w, y // self._bucket_h)

    def _index(self):
        for w in self.walls:
            bx0, by0 = self._bucket(w.rect.left, w.rect.top)
            bx1, by1 = self._bucket(w.rect.right, w.rect.bottom)
            for bx in range(bx0, bx1 + 1):
                for by in range(by0, by1 + 1):
                    self._grid.setdefault((bx, by), []).append(w)

    def _nearby(self, rect: pygame.Rect) -> list[WallTile | WallPolygon]:
        bx0, by0 = self._bucket(rect.left, rect.top)
        bx1, by1 = self._bucket(rect.right, rect.bottom)
        seen: set[int] = set()
        result: list[WallTile | WallPolygon] = []
        for bx in range(bx0, bx1 + 1):
            for by in range(by0, by1 + 1):
                for w in self._grid.get((bx, by), []):
                    wid = id(w)
                    if wid not in seen:
                        seen.add(wid)
                        result.append(w)
        return result

    def _segments_intersect(self, a, b, c, d) -> bool:
        def orient(p, q, r):
            return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

        def on_segment(p, q, r):
            return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and
                    min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))

        o1 = orient(a, b, c)
        o2 = orient(a, b, d)
        o3 = orient(c, d, a)
        o4 = orient(c, d, b)

        if o1 == 0 and on_segment(a, c, b):
            return True
        if o2 == 0 and on_segment(a, d, b):
            return True
        if o3 == 0 and on_segment(c, a, d):
            return True
        if o4 == 0 and on_segment(c, b, d):
            return True
        return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)

    def _polygon_collides_rect(self, polygon: WallPolygon, rect: pygame.Rect) -> bool:
        if not polygon.rect.colliderect(rect):
            return False

        rect_points = [rect.topleft, rect.topright, rect.bottomright, rect.bottomleft]
        rect_edges = list(zip(rect_points, rect_points[1:] + rect_points[:1]))
        poly_edges = list(zip(polygon.points, polygon.points[1:]))
        if polygon.closed:
            poly_edges.append((polygon.points[-1], polygon.points[0]))

        for start, end in poly_edges:
            if rect.clipline(start, end):
                return True

        for a, b in rect_edges:
            for c, d in poly_edges:
                if self._segments_intersect(a, b, c, d):
                    return True

        return False

    def _shape_collides_rect(self, shape: WallTile | WallPolygon, rect: pygame.Rect) -> bool:
        if isinstance(shape, WallPolygon):
            return self._polygon_collides_rect(shape, rect)
        return rect.colliderect(shape.rect)

    def _collides_any(self, rect: pygame.Rect) -> bool:
        return any(self._shape_collides_rect(w, rect) for w in self._nearby(rect))

    def _resolve_polygon(self, rect: pygame.Rect, polygon: WallPolygon) -> None:
        if not self._polygon_collides_rect(polygon, rect):
            return

        candidates: list[tuple[int, int, int]] = []
        limits = (
            ("left", rect.right - polygon.rect.left + 1),
            ("right", polygon.rect.right - rect.left + 1),
            ("up", rect.bottom - polygon.rect.top + 1),
            ("down", polygon.rect.bottom - rect.top + 1),
        )

        for direction, max_distance in limits:
            for distance in range(1, max(1, int(max_distance)) + 1):
                probe = rect.copy()
                if direction == "left":
                    probe.x -= distance
                    dx, dy = -distance, 0
                elif direction == "right":
                    probe.x += distance
                    dx, dy = distance, 0
                elif direction == "up":
                    probe.y -= distance
                    dx, dy = 0, -distance
                else:
                    probe.y += distance
                    dx, dy = 0, distance

                if not self._polygon_collides_rect(polygon, probe):
                    candidates.append((distance, dx, dy))
                    break

        if candidates:
            _, dx, dy = min(candidates, key=lambda item: item[0])
            rect.x += dx
            rect.y += dy

    # ── разрешение коллизий (MTV по осям) ─────────────────────────────────────
    def resolve(self, rect: pygame.Rect) -> pygame.Rect:
        """
        Сдвигает rect, чтобы он не перекрывал стены.
        Возвращает исправленный rect (объект изменяется на месте).
        """
        for w in self._nearby(rect):
            if isinstance(w, WallPolygon):
                self._resolve_polygon(rect, w)
                continue

            if not rect.colliderect(w.rect):
                continue

            # Перекрытия по каждой оси
            over_x_left = rect.right - w.rect.left
            over_x_right = w.rect.right - rect.left
            over_y_up = rect.bottom - w.rect.top
            over_y_down = w.rect.bottom - rect.top

            ox = over_x_left if over_x_left < over_x_right else -over_x_right
            oy = over_y_up if over_y_up < over_y_down else -over_y_down

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
        return self._collides_any(probe)

    # ── отладочная отрисовка ──────────────────────────────────────────────────
    def debug_draw(self, screen: pygame.Surface,
                   camera_x: int = 0, camera_y: int = 0):
        sw, sh = screen.get_size()
        for w in self.walls:
            rx = w.rect.x - camera_x
            ry = w.rect.y - camera_y
            if rx > sw or ry > sh or rx + w.rect.w < 0 or ry + w.rect.h < 0:
                continue
            if isinstance(w, WallPolygon):
                points = [(x - camera_x, y - camera_y) for x, y in w.points]
                if len(points) >= 2:
                    pygame.draw.lines(screen, (220, 50, 50), w.closed, points, 2)
            else:
                pygame.draw.rect(screen, (220, 50, 50),
                                 (rx, ry, w.rect.w, w.rect.h), 1)
