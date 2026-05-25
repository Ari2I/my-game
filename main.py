import pygame
import sys
from core.player import Player
from core.map import Map


def run():
    pygame.init()
    screen_width = 1200
    screen_height = 900
    screen = pygame.display.set_mode((screen_width, screen_height))

    # Создаём карту с островом
    game_map = Map(screen_width, screen_height, tile_size=64)

    # Создаём игрока в центре острова
    center_x = (game_map.map_width // 2) * 64
    center_y = (game_map.map_height // 2) * 64
    player = Player(center_x, center_y)

    clock = pygame.time.Clock()
    pygame.display.set_caption('Island Level')


    while True:
        clock.tick(60)
        for users_event in pygame.event.get():
            if users_event.type == pygame.QUIT:
                sys.exit()
        keys = pygame.key.get_pressed()
        player.update_player(keys)

        # Камера следует за игроком
        camera_x = player.rect.centerx - screen_width // 2
        camera_y = player.rect.centery - screen_height // 2

        # Отрисовка
        screen.fill((0, 49, 83))  # Цвет воды для фона

        # Рисуем карту
        game_map.draw(screen, camera_x, camera_y)

        # Рисуем точки спавна для отладки (можно убрать в продакшене)
        game_map.draw_spawn_points(screen, camera_x, camera_y)

        # Рисуем игрока
        player.draw(screen)

        pygame.display.flip()


run()
