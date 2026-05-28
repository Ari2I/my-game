import pygame
from core.map import TileMap
from core.player import Player

pygame.init()

WIDTH = 1920
HEIGHT = 1080

screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

game_map = TileMap("images/maps/mapV1.tmx")

# Получаем размеры карты в пикселях (с учётом масштаба тайлов)
map_width_px = game_map.tmx_data.width * game_map.tile_width
map_height_px = game_map.tmx_data.height * game_map.tile_height

# Создаём игрока в центре карты
center_x = map_width_px // 2
center_y = map_height_px // 2
player = Player(center_x, center_y)

running = True

while running:
    clock.tick(120)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Обновляем игрока
    keys = pygame.key.get_pressed()
    player.update_player(keys)

    # Камера следует за игроком (центрируем на игроке)
    camera_x = player.rect.centerx - WIDTH // 2
    camera_y = player.rect.centery - HEIGHT // 2

    # Ограничиваем камеру границами карты
    camera_x = max(0, min(camera_x, map_width_px - WIDTH))
    camera_y = max(0, min(camera_y, map_height_px - HEIGHT))

    screen.fill((39, 42, 57))

    # Рисуем карту с учётом камеры
    game_map.draw(screen, camera_x, camera_y)

    # Рисуем игрока с учётом камеры
    player.draw(screen, camera_x, camera_y)

    pygame.display.flip()

pygame.quit()
