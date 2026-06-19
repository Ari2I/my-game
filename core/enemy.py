"""
core/enemy.py — базовый класс для всех врагов.

Принцип SRP: Enemy содержит только общие данные и общую логику.
Конкретные FSM-состояния реализуются в дочерних классах через _run_state_machine().

Принцип OCP: добавление нового врага не требует изменения EnemyManager —
достаточно создать подкласс Enemy.

Принцип LSP: любой наследник Enemy совместим с EnemyManager.
"""

import pygame
import math
import random

# ─── Разделяемые константы ────────────────────────────────────────────────────
SEPARATION_RADIUS = 50
SEPARATION_FORCE = 2.5


class Enemy:
    """
    Базовый класс врага. Содержит:
      - общие поля (позиция, HP, скорость, урон и т.д.)
      - общую логику получения урона
      - общий каркас update() с вызовом _run_state_machine()
      - разделение с другими врагами (_separate)
      - синхронизацию rect (_sync_rect)
      - переключение состояния (_enter)

    Дочерние классы ОБЯЗАНЫ реализовать:
      - _run_state_machine(self, player, dt_sec, pdx, pdy, dist)
      - on_death(self, player)  — можно переопределить для своих наград
    """

    # Размер хитбокса — переопределить в подклассе при необходимости
    HITBOX_SIZE: int = 32

    def __init__(self, x: float, y: float, wave: int,
                 max_hp: float, speed: float, damage: float):
        self.x = float(x)
        self.y = float(y)
        self.wave = wave

        self.max_hp = max_hp
        self.hp = max_hp
        self.speed = speed
        self.damage = damage

        self.alive: bool = True
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.state: str = "idle"

        self._state_timer: float = 0.0
        self._attack_cd: float = random.uniform(0, 1.0)

        self.rect = pygame.Rect(0, 0, self.HITBOX_SIZE, self.HITBOX_SIZE)
        self._sync_rect()

    # ── синхронизация rect ────────────────────────────────────────────────────
    def _sync_rect(self):
        """Выравнивает rect.center по (x, y)."""
        self.rect.center = (int(self.x), int(self.y))

    # ── переключение состояний ────────────────────────────────────────────────
    def _enter(self, state: str):
        """Переходим в новое состояние, сбрасываем таймер."""
        self.state = state
        self._state_timer = 0.0

    # ── получение урона ───────────────────────────────────────────────────────
    def take_damage(self, amount: float):
        """Нанести урон. Дочерние классы могут расширить (эффекты, стан)."""
        if not self.alive:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            self.state = "dead"

    # ── смерть ────────────────────────────────────────────────────────────────
    def on_death(self, player):
        """
        Вызывается EnemyManager при гибели врага.
        Переопределять в подклассах для различных наград.
        """
        pass

    # ── разделение (anti-clustering) ─────────────────────────────────────────
    def _separate(self, others: list, dt: float):
        """Отталкивает врага от других врагов, чтобы они не стакались."""
        for o in others:
            if o is self or not o.alive:
                continue
            ddx = self.x - o.x
            ddy = self.y - o.y
            d = math.hypot(ddx, ddy)
            if 0 < d < SEPARATION_RADIUS:
                push = SEPARATION_FORCE * (SEPARATION_RADIUS - d) / SEPARATION_RADIUS
                self.x += (ddx / d) * push * dt
                self.y += (ddy / d) * push * dt

    # ── основной update ───────────────────────────────────────────────────────
    def update(self, player, dt: float, map_w: int, map_h: int, others: list):
        """
        Общий каркас обновления:
          1. Обновляем таймеры.
          2. Вызываем _run_state_machine() — реализуется в подклассах.
          3. Применяем скорость, разделение, ограничение карты.
        """
        if not self.alive:
            return

        dt_sec = dt / 60.0
        self._state_timer += dt_sec
        self._attack_cd = max(0.0, self._attack_cd - dt_sec)

        # Вектор к игроку (от хитбокса — стабильные координаты ног)
        player_cx = player.hitbox.centerx
        player_cy = player.hitbox.centery
        pdx = player_cx - self.x
        pdy = player_cy - self.y
        dist = math.hypot(pdx, pdy)

        self._run_state_machine(player, dt_sec, dt, pdx, pdy, dist)

        self.x += self.vx * dt
        self.y += self.vy * dt

        self._separate(others, dt)

        half = self.HITBOX_SIZE // 2
        self.x = max(half, min(self.x, map_w - half))
        self.y = max(half, min(self.y, map_h - half))
        self._sync_rect()

    def _run_state_machine(self, player, dt_sec: float, dt: float,
                           pdx: float, pdy: float, dist: float):
        """
        Реализует FSM конкретного врага.
        Обязан быть переопределён в подклассе.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} должен реализовать _run_state_machine()"
        )


# ─── Менеджер врагов ─────────────────────────────────────────────────────────
class EnemyManager:
    """
    Универсальный менеджер для любых врагов-наследников Enemy.

    Принцип OCP: не знает о конкретных типах врагов —
    работает через общий интерфейс Enemy.
    """

    EDGE_MARGIN: int = 450  # отступ от края карты при спавне (3 тайла × 64px)

    def __init__(self, map_w: int, map_h: int):
        self.map_w = map_w
        self.map_h = map_h
        self.enemies: list[Enemy] = []
        self._to_die: list[Enemy] = []

    # ── спавн ─────────────────────────────────────────────────────────────────
    def _edge_pos(self) -> tuple[float, float]:
        """Случайная позиция на краях карты с отступом EDGE_MARGIN."""
        m = self.EDGE_MARGIN
        if self.map_w <= m * 2 or self.map_h <= m * 2:
            return self.map_w / 2, self.map_h / 2
        import random
        s = random.randint(0, 3)
        if s == 0:
            return random.randint(m, self.map_w - m), m
        elif s == 1:
            return random.randint(m, self.map_w - m), self.map_h - m
        elif s == 2:
            return m, random.randint(m, self.map_h - m)
        else:
            return self.map_w - m, random.randint(m, self.map_h - m)

    def add(self, enemy: Enemy):
        """Добавить заранее созданного врага в менеджер."""
        self.enemies.append(enemy)

    # ── обновление ────────────────────────────────────────────────────────────
    def update(self, player, dt: float):
        """Обновляет всех врагов, обрабатывает гибель."""
        alive = []
        for e in self.enemies:
            e.update(player, dt, self.map_w, self.map_h, self.enemies)
            if not e.alive:
                self._to_die.append(e)
            else:
                alive.append(e)

        for dead in self._to_die:
            dead.on_death(player)
        self._to_die.clear()
        self.enemies = alive

    # ── урон по всем врагам в конусе ─────────────────────────────────────────
    def apply_damage(self, player):
        """Наносит урон от атаки игрока всем врагам в конусе."""
        dmg = player.stats.damage()
        for e in self.enemies:
            if player.point_in_attack_cone(e.x, e.y):
                e.take_damage(dmg)

    @property
    def count(self) -> int:
        return len(self.enemies)
