import pygame
import pytmx


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

    def draw(self, screen, camera_x=0, camera_y=0):  # scale=4 даст 16*4=64 пикселя на тайл
        for layer in self._iter_tile_layers(self.tmx_data.visible_layers):
            for x, y, gid in layer:
                tile = self.tmx_data.get_tile_image_by_gid(gid)
                if tile:
                    # Масштабируем тайл в 4 раза
                    scaled_tile = pygame.transform.scale(tile, (self.tile_width, self.tile_height))
                    screen.blit(scaled_tile, (x * self.tile_width - camera_x, y * self.tile_height - camera_y))