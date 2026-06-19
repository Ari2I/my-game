"""
core/render/slime_renderer.py — отрисовка слаймов (View).

SlimeRenderer не хранит ссылку на конкретный слайм (т.к. рисует много
разных экземпляров) — модель передаётся как параметр в draw().
SlimeManagerRenderer обходит SlimeManager.slimes и вызывает SlimeRenderer
для каждого живого слайма.

Доступ к приватным полям модели (_hit_flash, _bounce_phase, _squash,
_state_timer) осуществляется через публичные read-only свойства
(hit_flash, bounce_phase, squash, state_timer), объявленные в core.slime.Slime.
"""

import math
import pygame

from core.slime import State, SLIME_RADIUS

# ─── Цвета (перенесены из core/slime.py) ──────────────────────────────────────
C_BODY = (70, 175, 70)
C_BODY_DARK = (45, 120, 45)
C_BODY_RED = (200, 80, 50)
C_BODY_LUNGE = (120, 220, 90)
C_BODY_STUN = (180, 180, 60)
C_EYE = (255, 255, 255)
C_PUPIL = (20, 20, 20)
C_HILITE = (160, 230, 160)
C_HP_BG = (35, 10, 10)
C_HP_FILL = (90, 210, 70)


class SlimeRenderer:
    """Отрисовка одного слайма. Модель передаётся в draw() как параметр."""

    def draw(self, slime, screen, camera_x=0, camera_y=0):
        if not slime.alive:
            return

        sx = int(slime.x) - camera_x
        sy = int(slime.y) - camera_y

        bounce_y = 0
        if slime.state in (State.APPROACH, State.WANDER):
            bounce_y = int(math.sin(slime.bounce_phase) * 5)

        shake_x = 0
        if slime.state == State.PREPARE:
            shake_x = int(math.sin(slime.state_timer * 42) * 3)

        cx = sx + shake_x
        cy = sy + bounce_y

        if slime.hit_flash > 0:
            body_color = C_BODY_RED
        elif slime.state == State.STUNNED:
            body_color = C_BODY_STUN
        elif slime.state == State.LUNGE:
            body_color = C_BODY_LUNGE
        elif slime.state == State.WANDER:
            body_color = C_BODY_DARK
        else:
            body_color = C_BODY

        sq = max(0.5, min(slime.squash, 1.4))
        rw = int(SLIME_RADIUS * 2 * (2.0 - sq))
        rh = int(SLIME_RADIUS * 2 * sq * 0.9)

        body_rect = pygame.Rect(cx - rw // 2,
                                cy - rh // 2 + (SLIME_RADIUS - rh // 2),
                                rw, rh)
        pygame.draw.ellipse(screen, body_color, body_rect)
        pygame.draw.ellipse(screen, C_BODY_DARK, body_rect, width=1)

        # блик
        hi_w = max(4, rw // 3)
        hi_h = max(3, rh // 4)
        hi = pygame.Surface((hi_w, hi_h), pygame.SRCALPHA)
        pygame.draw.ellipse(hi, (*C_HILITE, 110), hi.get_rect())
        screen.blit(hi, (cx - rw // 4, cy - rh // 3 + (SLIME_RADIUS - rh // 2)))

        # глаза
        for ex_off in (-7, 7):
            ex = cx + ex_off
            ey = cy - rh // 3
            pygame.draw.circle(screen, C_EYE, (ex, ey), 5)
            po = (1, 2) if slime.state == State.WANDER else (1, 0)
            pygame.draw.circle(screen, C_PUPIL, (ex + po[0], ey + po[1]), 2)

        # HP-бар
        bw, bh = 38, 5
        bx = cx - bw // 2
        by = cy - SLIME_RADIUS - 12
        pygame.draw.rect(screen, C_HP_BG, (bx, by, bw, bh), border_radius=2)
        filled = int(bw * slime.hp / slime.max_hp) if slime.max_hp > 0 else 0
        if filled > 0:
            pygame.draw.rect(screen, C_HP_FILL, (bx, by, filled, bh), border_radius=2)
        pygame.draw.rect(screen, (0, 0, 0), (bx, by, bw, bh), width=1, border_radius=2)


class SlimeManagerRenderer:
    """Отрисовка всех слаймов менеджера SlimeManager."""

    def __init__(self):
        self._slime_renderer = SlimeRenderer()

    def draw(self, manager, screen, camera_x=0, camera_y=0):
        for slime in manager.slimes:
            self._slime_renderer.draw(slime, screen, camera_x, camera_y)
