import pygame



def load_tiles(path, tile_size):
    image = pygame.image.load(path).convert_alpha()
    tiles = []

    for y in range(0, image.get_height(), tile_size):
        for x in range(0, image.get_width(), tile_size):
            tile = image.subsurface((x, y, tile_size, tile_size))
            tiles.append(tile)

    return tiles