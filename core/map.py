import pygame
import pytmx


class TileMap:

    def __init__(self, filename):
        self.tmx_data = pytmx.load_pygame(filename)

    def draw(self, screen):

        for layer in self.tmx_data.visible_layers:

            if isinstance(layer, pytmx.TiledTileLayer):

                for x, y, gid in layer:

                    tile = self.tmx_data.get_tile_image_by_gid(gid)

                    if tile:
                        screen.blit(tile, (x * 16, y * 16))