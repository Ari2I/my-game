import pygame
import sys
from core.player import Player





def run():
    pygame.init()
    screen = pygame.display.set_mode((1200, 900))
    player = Player(600, 450)
    clock = pygame.time.Clock()
    pygame.display.set_caption('first try')



    while True:
        clock.tick(60)
        for users_event in pygame.event.get():
            if users_event.type == pygame.QUIT:
                sys.exit()
        keys = pygame.key.get_pressed()
        player.update_player(keys)

        screen.fill((0, 49, 83))
        player.draw(screen)

        pygame.display.flip()

run()