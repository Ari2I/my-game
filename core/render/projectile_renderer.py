"""
core/render/projectile_renderer.py — отрисовка снарядов (View).

Принцип SRP: только отрисовка, логика в core/projectile.py.
"""

import math
import pygame


# ─── Цвета ────────────────────────────────────────────────────────────────────
C_PROJ_CORE  = (255, 120,  40)   # оранжевое ядро
C_PROJ_GLOW  = (255, 200,  80)   # жёлтое свечение
C_PROJ_TRAIL = (180,  60,  20)   # тёмный след


class ProjectileRenderer:
    """Отрисовка одного снаряда."""

    def draw(self, projectile, screen, camera_x=0, camera_y=0):
        if not projectile.alive:
            return

        sx = int(projectile.x) - camera_x
        sy = int(projectile.y) - camera_y
        r  = projectile.RADIUS

        # Небольшой след (3 точки позади)
        speed  = math.hypot(projectile.vx, projectile.vy)
        if speed > 0:
            dx = projectile.vx / speed
            dy = projectile.vy / speed
            for i in range(1, 4):
                trail_x = sx - int(dx * i * 4)
                trail_y = sy - int(dy * i * 4)
                alpha   = max(0, 180 - i * 55)
                trail_r = max(1, r - i)
                trail_s = pygame.Surface((trail_r * 2 + 2, trail_r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(trail_s, (*C_PROJ_TRAIL, alpha),
                                   (trail_r + 1, trail_r + 1), trail_r)
                screen.blit(trail_s, (trail_x - trail_r - 1, trail_y - trail_r - 1))

        # Свечение (полупрозрачный круг чуть больше)
        glow_r = r + 3
        glow_s = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_s, (*C_PROJ_GLOW, 80),
                           (glow_r + 1, glow_r + 1), glow_r)
        screen.blit(glow_s, (sx - glow_r - 1, sy - glow_r - 1))

        # Ядро
        pygame.draw.circle(screen, C_PROJ_CORE, (sx, sy), r)
        pygame.draw.circle(screen, C_PROJ_GLOW, (sx, sy), max(1, r - 2))