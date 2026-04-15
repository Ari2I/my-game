import pygame
import sys

def event(player):
    for users_event in pygame.event.get():
        if users_event.type == pygame.QUIT:
            sys.exit()
        elif users_event.type == pygame.KEYDOWN:
            if users_event.key == pygame.K_d:
                player.mRight = True
            if users_event.key == pygame.K_a:
                player.mLeft = True
            if users_event.key == pygame.K_w:
                player.mUp = True
            if users_event.key == pygame.K_s:
                player.mDown = True
        elif users_event.type == pygame.KEYUP:
            if users_event.key == pygame.K_d:
                player.mRight = False
            if users_event.key == pygame.K_a:
                player.mLeft = False
            if users_event.key == pygame.K_w:
                player.mUp = False
            if users_event.key == pygame.K_s:
                player.mDown = False

