"""
core/render/ranged_enemy_renderer.py — отрисовка дальнего врага (View).

Принцип SRP: только отрисовка, логика в core/ranged_enemy.py.
"""

import math
import pygame

from core.ranged_enemy import RangedState

# ─── Цвета ────────────────────────────────────────────────────────────────────
C_BODY = (80, 60, 140)  # фиолетово-синий корпус
C_BODY_DARK = (50, 35, 95)
C_BODY_RED = (180, 60, 60)
C_BODY_AIM = (130, 90, 200)  # при прицеливании светлеет
C_BODY_STUN = (150, 150, 80)
C_EYE = (255, 230, 80)  # жёлтые глаза
C_PUPIL = (20, 20, 20)
C_AIM_RING = (255, 100, 50)  # кольцо прицела
C_HP_BG = (30, 10, 30)
C_HP_FILL = (120, 80, 200)

ENEMY_RADIUS = 22  # визуальный радиус


class RangedEnemyRenderer:
    """Отрисовка одного дальнего врага."""

    def draw(self, enemy, screen, camera_x=0, camera_y=0):
        if not enemy.alive:
            return

        sx = int(enemy.x) - camera_x
        sy = int(enemy.y) - camera_y

        # Дрожание при ударе
        shake_x = 0
        if enemy.hit_flash > 0:
            import random
            shake_x = random.randint(-2, 2)

        cx = sx + shake_x
        cy = sy

        # Цвет корпуса
        if enemy.hit_flash > 0:
            body_color = C_BODY_RED
        elif enemy.state == RangedState.STUNNED:
            body_color = C_BODY_STUN
        elif enemy.state == RangedState.AIM:
            body_color = C_BODY_AIM
        else:
            body_color = C_BODY

        # Ромбовидное тело (4 точки)
        r = ENEMY_RADIUS
        diamond = [
            (cx, cy - r),  # верх
            (cx + r, cy),  # право
            (cx, cy + r),  # низ
            (cx - r, cy),  # лево
        ]
        pygame.draw.polygon(screen, body_color, diamond)
        pygame.draw.polygon(screen, C_BODY_DARK, diamond, 2)

        # Блик
        hi_pts = [
            (cx - 4, cy - r + 4),
            (cx + 4, cy - r + 4),
            (cx + 2, cy - 4),
            (cx - 2, cy - 4),
        ]
        hi_s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.polygon(screen, (200, 180, 255, 60), hi_pts)

        # Глаза
        for ex_off in (-6, 6):
            ex = cx + ex_off
            ey = cy - 3
            pygame.draw.circle(screen, C_EYE, (ex, ey), 4)
            pygame.draw.circle(screen, C_PUPIL, (ex + 1, ey + 1), 2)

        # Кольцо прицела при AIM
        if enemy.state == RangedState.AIM and enemy.aim_progress > 0:
            ring_r = int(r * 1.5 + (1.0 - enemy.aim_progress) * r)
            alpha = int(enemy.aim_progress * 200)
            ring_s = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring_s, (*C_AIM_RING, alpha),
                               (ring_r + 2, ring_r + 2), ring_r, 2)
            screen.blit(ring_s, (cx - ring_r - 2, cy - ring_r - 2))

        # HP-бар
        bw, bh = 40, 5
        bx = cx - bw // 2
        by = cy - ENEMY_RADIUS - 12
        pygame.draw.rect(screen, C_HP_BG, (bx, by, bw, bh), border_radius=2)
        filled = int(bw * enemy.hp / enemy.max_hp) if enemy.max_hp > 0 else 0
        if filled > 0:
            pygame.draw.rect(screen, C_HP_FILL, (bx, by, filled, bh), border_radius=2)
        pygame.draw.rect(screen, (0, 0, 0), (bx, by, bw, bh), width=1, border_radius=2)


class RangedEnemyManagerRenderer:
    """Отрисовка всех дальних врагов и их снарядов."""

    def __init__(self):
        self._enemy_renderer = RangedEnemyRenderer()
        from core.render.projectile_renderer import ProjectileRenderer
        self._projectile_renderer = ProjectileRenderer()

    def draw(self, manager, screen, camera_x=0, camera_y=0):
        """Рисует ВСЕХ дальних врагов и снаряды одним проходом (без Y-сортировки)."""
        for enemy in manager.enemies:
            self._enemy_renderer.draw(enemy, screen, camera_x, camera_y)
        for proj in manager.projectiles:
            self._projectile_renderer.draw(proj, screen, camera_x, camera_y)

    def draw_one(self, enemy, screen, camera_x=0, camera_y=0):
        """
        Рисует ОДНОГО дальнего врага (без снарядов — они летят поверх всего
        и рисуются отдельно в main.py после Y-сортировки).
        Используется YSortRenderer.
        """
        self._enemy_renderer.draw(enemy, screen, camera_x, camera_y)

    def draw_projectiles(self, manager, screen, camera_x=0, camera_y=0):
        """Рисует только снаряды — отдельно, поверх Y-сортированной сцены."""
        for proj in manager.projectiles:
            self._projectile_renderer.draw(proj, screen, camera_x, camera_y)
