import pygame

class Player():

    def __init__(self, screen):
        """инициализация игрока"""

        self.screen = screen
        self.image = pygame.image.load('images/player.png')
        self.rect =  self.image.get_rect()
        self.screen_rect = screen.get_rect()
        self.rect.centerx = self.screen_rect.centerx
        self.rect.centery = self.screen_rect.centery
        self.mRight = False
        self.mLeft = False
        self.mUp = False
        self.mDown = False

    def output(self):
        """отрисовка игрока"""
        self.screen.blit(self.image, self.rect)

    def update_player(self):
        """обновление позиции игрока"""
        if self.mRight and self.rect.right < self.screen_rect.right:
            self.rect.centerx += 10
        if self.mLeft and self.rect.left > self.screen_rect.left:
            self.rect.centerx -= 10
        if self.mUp and self.rect.top > self.screen_rect.top:
            self.rect.centery -= 10
        if self.mDown and self.rect.bottom < self.screen_rect.bottom:
            self.rect.centery += 10
