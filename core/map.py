import pygame
import pytmx


class TileMap:

    def __init__(self, filename):
        self.tmx_data = pytmx.load_pygame(filename)
        self.tile_scale = 4  # Масштаб увеличения тайлов (в 4 раза)
        self.tile_width = 16 * self.tile_scale  # 64 пикселя
        self.tile_height = 16 * self.tile_scale  # 64 пикселя


    def draw(self, screen, camera_x=0, camera_y=0):  # scale=4 даст 16*4=64 пикселя на тайл
        for layer in self.tmx_data.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid in layer:
                    tile = self.tmx_data.get_tile_image_by_gid(gid)
                    if tile:
                        # Масштабируем тайл в 4 раза
                        scaled_tile = pygame.transform.scale(tile, (self.tile_width, self.tile_height))
                        screen.blit(scaled_tile, (x * self.tile_width - camera_x, y * self.tile_height - camera_y))