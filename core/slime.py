"""
core/slime.py — враг «Слайм» v2.

Машина состояний: WANDER → APPROACH → PREPARE → LUNGE → ATTACK/RECOIL → STUNNED

Ключевые улучшения:
  • Слайм подходит с любой стороны — орбитальный смещение при APPROACH
    гарантирует что несколько слаймов атакуют с разных углов.
  • Задержка урона: ATTACK_COOLDOWN + i-frames на игроке.
  • Разделение между слаймами (anti-clustering).

Отрисовка вынесена в core/render/slime_renderer.py (PlayerRenderer/SlimeRenderer
не хранятся здесь — этот модуль не знает о pygame.draw/screen.blit).
"""

import pygame
import math
import random

# ─── Константы ────────────────────────────────────────────────────────────────
SLIME_BASE_HP      = 30
SLIME_BASE_SPEED   = 1.4
SLIME_LUNGE_SPEED  = 7.0
SLIME_BASE_DAMAGE  = 5
SLIME_XP_REWARD    = 25
SLIME_GOO_DROP_MAX = 2

DETECT_RANGE    = 380
PREPARE_RANGE   = 105
ATTACK_RANGE    = 50
ATTACK_COOLDOWN = 1.3    # сек между ударами слайма
PREPARE_TIME    = 0.45
STUN_TIME       = 0.35
RECOIL_TIME     = 0.5
RECOIL_SPEED    = 4.0

SEPARATION_RADIUS = 50
SEPARATION_FORCE  = 2.5

SLIME_RADIUS = 20

# Орбитальный «предпочтительный» угол — у каждого слайма свой,
# чтобы они окружали игрока с разных сторон
ORBIT_SPREAD = 55.0   # °, насколько слайм отклоняется от прямой к цели


class State:
    WANDER  = "wander"
    APPROACH= "approach"
    PREPARE = "prepare"
    LUNGE   = "lunge"
    ATTACK  = "attack"
    RECOIL  = "recoil"
    STUNNED = "stunned"
    DEAD    = "dead"


class Slime:
    def __init__(self, x: float, y: float, wave: int = 1):
        self.x = float(x)
        self.y = float(y)

        scale = 1.0 + (wave - 1) * 0.25
        self.max_hp = SLIME_BASE_HP    * scale
        self.hp     = self.max_hp
        self.speed  = SLIME_BASE_SPEED * (1.0 + (wave - 1) * 0.08)
        self.damage = SLIME_BASE_DAMAGE * scale
        self.wave   = wave
        self.alive  = True

        self.vx: float = 0.0
        self.vy: float = 0.0

        # AI
        self.state: str     = State.WANDER
        self._state_timer   = 0.0
        self._attack_cd     = random.uniform(0, ATTACK_COOLDOWN)  # разброс старта

        # WANDER
        angle = random.uniform(0, math.pi * 2)
        self._wander_dx     = math.cos(angle)
        self._wander_dy     = math.sin(angle)
        self._wander_timer  = random.uniform(0.8, 2.5)

        # LUNGE — запомненная цель
        self._lunge_tx: float = 0.0
        self._lunge_ty: float = 0.0

        # Орбитальный угол-смещение — у каждого слайма свой, фиксированный
        # Это заставляет их подходить с разных сторон
        self._orbit_offset = random.uniform(-ORBIT_SPREAD, ORBIT_SPREAD)

        # Визуал (читается рендерером через свойства ниже)
        self._hit_flash     = 0.0
        self._bounce_phase  = random.uniform(0, math.pi * 2)
        self._squash        = 1.0

        self.rect = pygame.Rect(0, 0, SLIME_RADIUS * 2, SLIME_RADIUS * 2)
        self._sync_rect()

    def _sync_rect(self):
        self.rect.center = (int(self.x), int(self.y))

    def _enter(self, s: str):
        self.state = s
        self._state_timer = 0.0

    # ── свойства для рендерера ──────────────────────────────────────────────
    # Публичный read-only доступ к визуальным полям, которые нужны
    # core.render.slime_renderer.SlimeRenderer для отрисовки.
    @property
    def hit_flash(self) -> float:
        return self._hit_flash

    @property
    def bounce_phase(self) -> float:
        return self._bounce_phase

    @property
    def squash(self) -> float:
        return self._squash

    @property
    def state_timer(self) -> float:
        return self._state_timer

    # ─────────────────────────────────────────────────────────────────────────
    def update(self, player, dt: float, map_w: int, map_h: int, others: list):
        if not self.alive:
            return

        dt_sec = dt / 60.0

        self._state_timer += dt_sec
        self._hit_flash    = max(0.0, self._hit_flash - dt_sec)
        self._attack_cd    = max(0.0, self._attack_cd - dt_sec)

        pdx = player.rect.centerx - self.x
        pdy = player.rect.centery - self.y
        dist = math.hypot(pdx, pdy)

        if   self.state == State.STUNNED:  self._do_stunned(dt_sec)
        elif self.state == State.WANDER:   self._do_wander(dt_sec, dt, dist)
        elif self.state == State.APPROACH: self._do_approach(dt, pdx, pdy, dist)
        elif self.state == State.PREPARE:  self._do_prepare(dt_sec, pdx, pdy, dist)
        elif self.state == State.LUNGE:    self._do_lunge(dt, dt_sec, dist)
        elif self.state == State.ATTACK:   self._do_attack(dt_sec, pdx, pdy, dist, player)
        elif self.state == State.RECOIL:   self._do_recoil(dt, dt_sec, dist)

        # анимация
        if self.state in (State.APPROACH, State.WANDER):
            self._bounce_phase += 5.0 * dt_sec
        elif self.state == State.LUNGE:
            self._squash = max(0.6, self._squash - 0.08 * dt)

        self.x += self.vx * dt
        self.y += self.vy * dt

        self._separate(others, dt)

        self.x = max(SLIME_RADIUS, min(self.x, map_w - SLIME_RADIUS))
        self.y = max(SLIME_RADIUS, min(self.y, map_h - SLIME_RADIUS))
        self._sync_rect()

    # ── состояния ─────────────────────────────────────────────────────────────

    def _do_stunned(self, dt_sec):
        self.vx *= 0.72
        self.vy *= 0.72
        if self._state_timer >= STUN_TIME:
            self._enter(State.APPROACH)

    def _do_wander(self, dt_sec, dt, dist):
        self._wander_timer -= dt_sec
        if self._wander_timer <= 0:
            a = random.uniform(0, math.pi * 2)
            self._wander_dx   = math.cos(a)
            self._wander_dy   = math.sin(a)
            self._wander_timer = random.uniform(1.0, 2.5)

        ws = self.speed * 0.45
        self.vx = self._wander_dx * ws
        self.vy = self._wander_dy * ws

        if dist < DETECT_RANGE:
            self._enter(State.APPROACH)

    def _do_approach(self, dt, pdx, pdy, dist):
        if dist > DETECT_RANGE * 1.3:
            self._enter(State.WANDER)
            return

        if dist <= PREPARE_RANGE:
            self.vx = 0; self.vy = 0
            self._enter(State.PREPARE)
            return

        if dist > 0:
            # Базовый угол к игроку
            base_angle = math.atan2(pdy, pdx)
            # Добавляем индивидуальное орбитальное смещение
            # Это рассеивает слаймов по окружности вокруг игрока
            offset_rad = math.radians(self._orbit_offset)
            final_angle = base_angle + offset_rad * max(0, (PREPARE_RANGE * 2 - dist) / (PREPARE_RANGE * 2))

            nx = math.cos(final_angle)
            ny = math.sin(final_angle)
            self.vx = nx * self.speed
            self.vy = ny * self.speed

    def _do_prepare(self, dt_sec, pdx, pdy, dist):
        self.vx *= 0.78
        self.vy *= 0.78

        if self._state_timer >= PREPARE_TIME:
            if dist > 0:
                nx, ny = pdx / dist, pdy / dist
            else:
                nx, ny = 1.0, 0.0
            self._lunge_tx = self.x + nx * dist * 1.1
            self._lunge_ty = self.y + ny * dist * 1.1
            self._squash   = 1.35
            self._enter(State.LUNGE)

    def _do_lunge(self, dt, dt_sec, dist_to_player):
        ldx = self._lunge_tx - self.x
        ldy = self._lunge_ty - self.y
        d   = math.hypot(ldx, ldy)

        if d > 0:
            nx, ny = ldx / d, ldy / d
            self.vx = nx * SLIME_LUNGE_SPEED
            self.vy = ny * SLIME_LUNGE_SPEED
        else:
            self.vx = self.vy = 0

        if d < 12 or self._state_timer > 0.40:
            self.vx = self.vy = 0
            self._squash = 0.65
            if dist_to_player <= ATTACK_RANGE:
                self._enter(State.ATTACK)
            else:
                self._enter(State.RECOIL)

    def _do_attack(self, dt_sec, pdx, pdy, dist, player):
        # Плавное торможение у игрока
        self.vx *= 0.82
        self.vy *= 0.82

        if dist > ATTACK_RANGE * 2.5:
            self._enter(State.APPROACH)
            return

        if self._attack_cd <= 0:
            player.take_damage(self.damage)   # i-frames на игроке фильтруют спам
            self._attack_cd = ATTACK_COOLDOWN
            # небольшой отскок после удара
            if dist > 0:
                nx, ny = pdx / dist, pdy / dist
                self.vx = -nx * 2.0
                self.vy = -ny * 2.0

    def _do_recoil(self, dt, dt_sec, dist):
        # отскакиваем в случайном направлении назад
        if self._state_timer < 0.02:
            a = math.atan2(self.vy, self.vx) + math.pi + random.uniform(-0.5, 0.5)
            self.vx = math.cos(a) * RECOIL_SPEED
            self.vy = math.sin(a) * RECOIL_SPEED

        self.vx *= 0.88
        self.vy *= 0.88
        self._squash = min(1.0, self._squash + 0.04 * dt)

        if self._state_timer >= RECOIL_TIME:
            self.vx = self.vy = 0
            self._squash = 1.0
            self._enter(State.APPROACH if dist < DETECT_RANGE else State.WANDER)

    # ── разделение ────────────────────────────────────────────────────────────
    def _separate(self, others: list, dt: float):
        for o in others:
            if o is self or not o.alive:
                continue
            ddx = self.x - o.x
            ddy = self.y - o.y
            d   = math.hypot(ddx, ddy)
            if 0 < d < SEPARATION_RADIUS:
                push = SEPARATION_FORCE * (SEPARATION_RADIUS - d) / SEPARATION_RADIUS
                self.x += (ddx / d) * push * dt
                self.y += (ddy / d) * push * dt

    # ── получение урона ───────────────────────────────────────────────────────
    def take_damage(self, amount: float):
        if not self.alive:
            return
        self.hp -= amount
        self._hit_flash = 0.18
        if self.state not in (State.DEAD, State.STUNNED):
            self._enter(State.STUNNED)
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
            self.state = State.DEAD

    def on_death(self, player):
        player.gain_xp(SLIME_XP_REWARD)
        player.inventory.slime_goo += random.randint(1, SLIME_GOO_DROP_MAX)


# ─── Менеджер ─────────────────────────────────────────────────────────────────
class SlimeManager:
    EDGE_MARGIN = 80

    def __init__(self, map_w: int, map_h: int):
        self.map_w = map_w
        self.map_h = map_h
        self.slimes: list[Slime] = []
        self._to_die: list[Slime] = []

    def spawn_wave(self, wave: int = 1, count: int = 5):
        for _ in range(count):
            x, y = self._edge_pos()
            self.slimes.append(Slime(x, y, wave=wave))

    def spawn_one(self, wave: int = 1):
        x, y = self._edge_pos()
        self.slimes.append(Slime(x, y, wave=wave))

    def _edge_pos(self):
        m = self.EDGE_MARGIN
        s = random.randint(0, 3)
        if   s == 0: return random.randint(m, self.map_w - m), m
        elif s == 1: return random.randint(m, self.map_w - m), self.map_h - m
        elif s == 2: return m,              random.randint(m, self.map_h - m)
        else:        return self.map_w - m, random.randint(m, self.map_h - m)

    def update(self, player, dt: float):
        alive = []
        for s in self.slimes:
            s.update(player, dt, self.map_w, self.map_h, self.slimes)
            (self._to_die if not s.alive else alive).append(s)
        for d in self._to_die:
            d.on_death(player)
        self._to_die.clear()
        self.slimes = alive

    def apply_damage_to_slimes(self, player):
        """Урон по конусу атаки игрока."""
        dmg = player.stats.damage()
        for s in self.slimes:
            if player.point_in_attack_cone(s.x, s.y):
                s.take_damage(dmg)

    @property
    def count(self):
        return len(self.slimes)