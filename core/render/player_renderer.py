"""
core/render/player_renderer.py — отрисовка игрока (View).

Отделяет отображение от модели core.player.Player (Model).
PlayerRenderer хранит ссылку на модель и только читает её публичные
поля/свойства (image, rect, is_attacking, is_invincible, get_attack_cone()),
не изменяя состояние модели и не зная ничего о вводе/логике игры.
"""

import math
import pygame


# ─── Параметры отладочной отрисовки конуса атаки ──────────────────────────────
C_CONE_FILL    = (255, 220, 50, 55)
C_CONE_OUTLINE = (255, 220, 50, 130)
CONE_STEPS     = 20

# ─── Параметры мигания во время i-frames ───────────────────────────────────────
IFRAME_FLASH_PERIOD_MS = 80     # период переключения видимой/невидимой фазы
IFRAME_FLASH_ALPHA     = 60
IFRAME_FLASH_COLOR     = (255, 255, 255)


class PlayerRenderer:
    """
    Использование:
        player_renderer = PlayerRenderer(player)
        ...
        player_renderer.draw(screen, camera_x, camera_y)
        player_renderer.draw_attack_cone(screen, camera_x, camera_y)
        player_renderer.draw_iframe_flash(screen, camera_x, camera_y)
    """

    def __init__(self, player):
        self.player = player

    # ── основной спрайт игрока ────────────────────────────────────────────────
    def draw(self, screen, camera_x=0, camera_y=0):
        player = self.player
        screen.blit(player.image, (player.rect.x - camera_x, player.rect.y - camera_y))

    # ── отладочная отрисовка конуса атаки ─────────────────────────────────────
    def draw_attack_cone(self, screen, camera_x=0, camera_y=0):
        """Рисует конус атаки (для отладки, вызвать до pygame.display.flip)."""
        player = self.player
        if not player.is_attacking:
            return

        ox, oy, dir_deg, half_deg, radius = player.get_attack_cone()
        sx, sy = int(ox) - camera_x, int(oy) - camera_y

        cone_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        start_a = math.radians(dir_deg - half_deg)
        end_a   = math.radians(dir_deg + half_deg)
        cx_s    = radius + 2
        cy_s    = radius + 2
        points  = [(cx_s, cy_s)]
        for i in range(CONE_STEPS + 1):
            a = start_a + (end_a - start_a) * i / CONE_STEPS
            points.append((cx_s + math.cos(a) * radius, cy_s + math.sin(a) * radius))

        pygame.draw.polygon(cone_surf, C_CONE_FILL, points)
        pygame.draw.polygon(cone_surf, C_CONE_OUTLINE, points, width=2)
        screen.blit(cone_surf, (sx - radius - 2, sy - radius - 2))

    # ── мигание во время неуязвимости (i-frames) ──────────────────────────────
    def draw_iframe_flash(self, screen, camera_x=0, camera_y=0):
        """Полупрозрачная белая вспышка поверх игрока во время i-frames."""
        player = self.player
        if not player.is_invincible:
            return
        if int(pygame.time.get_ticks() / IFRAME_FLASH_PERIOD_MS) % 2 != 0:
            return

        flash = pygame.Surface(player.rect.size, pygame.SRCALPHA)
        flash.fill((*IFRAME_FLASH_COLOR, IFRAME_FLASH_ALPHA))
        screen.blit(flash, (player.rect.x - camera_x, player.rect.y - camera_y))