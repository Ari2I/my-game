import pygame
import sys
from core.player import Player
import core.events as ev


def run():
    pygame.init()
    screen = pygame.display.set_mode((1200,900))
    clock = pygame.time.Clock()
    pygame.display.set_caption('first try')
    bg_color = (0,0,0)
    player = Player(screen)

    while True:
        ev.event(player)
        player.update_player()
        screen.fill(bg_color)
        player.output()
        pygame.display.flip()
        clock.tick(60)

run()