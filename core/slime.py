"""
core/slime.py — враг «Слайм».

Наследует Enemy (core/enemy.py).
Содержит только специфичную FSM-логику слайма:
  WANDER → APPROACH → PREPARE → LUNGE → ATTACK/RECOIL → STUNNED

Принцип SRP: вся отрисовка вынесена в core/render/slime_renderer.py.
Принцип LSP: Slime совместим с EnemyManager через интерфейс Enemy.
"""

import math
import random

from core.enemy import Enemy, EnemyManager
from core.loot import roll_loot, SLIME_LOOT_TABLE

# ─── Константы слайма ─────────────────────────────────────────────────────────
SLIME_BASE_HP = 30
SLIME_BASE_SPEED = 1.4
SLIME_LUNGE_SPEED = 7.0
SLIME_BASE_DAMAGE = 5
SLIME_XP_REWARD = 25

DETECT_RANGE = 380
PREPARE_RANGE = 105
ATTACK_RANGE = 50
SLIME_ATTACK_CD = 1.3
PREPARE_TIME = 0.45
STUN_TIME = 0.35
RECOIL_TIME = 0.5
RECOIL_SPEED = 4.0

ORBIT_SPREAD = 55.0  # °, орбитальное смещение при APPROACH

SLIME_RADIUS = 20  # визуальный радиус (для рендерера)


class State:
    WANDER = "wander"
    APPROACH = "approach"
    PREPARE = "prepare"
    LUNGE = "lunge"
    ATTACK = "attack"
    RECOIL = "recoil"
    STUNNED = "stunned"
    DEAD = "dead"


class Slime(Enemy):
    """
    Слайм — ближний враг с FSM из 7 состояний.
    Все общие поля/методы (x, y, hp, take_damage, _enter и т.д.)
    унаследованы от Enemy.
    """

    HITBOX_SIZE = SLIME_RADIUS * 2  # 40px

    def __init__(self, x: float, y: float, wave: int = 1):
        scale = 1.0 + (wave - 1) * 0.25

        super().__init__(
            x=x, y=y, wave=wave,
            max_hp=SLIME_BASE_HP * scale,
            speed=SLIME_BASE_SPEED * (1.0 + (wave - 1) * 0.08),
            damage=SLIME_BASE_DAMAGE * scale,
        )

        # Начальное состояние — блуждание
        self._enter(State.WANDER)
        self._attack_cd = random.uniform(0, SLIME_ATTACK_CD)

        # WANDER
        angle = random.uniform(0, math.pi * 2)
        self._wander_dx = math.cos(angle)
        self._wander_dy = math.sin(angle)
        self._wander_timer = random.uniform(0.8, 2.5)

        # LUNGE
        self._lunge_tx: float = 0.0
        self._lunge_ty: float = 0.0

        # Орбитальное смещение — у каждого слайма своё, атакуют с разных сторон
        self._orbit_offset = random.uniform(-ORBIT_SPREAD, ORBIT_SPREAD)

        # Визуальные поля (читаются рендерером через свойства)
        self._hit_flash = 0.0
        self._bounce_phase = random.uniform(0, math.pi * 2)
        self._squash = 1.0

    # ── публичные read-only свойства для рендерера ────────────────────────────
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

    # ── переопределяем take_damage: добавляем стан и вспышку ─────────────────
    def take_damage(self, amount: float):
        if not self.alive:
            return
        self.hp -= amount
        self._hit_flash = 0.18
        # Стан прерывает любое состояние кроме смерти
        if self.state not in (State.DEAD, State.STUNNED):
            self._enter(State.STUNNED)
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            self.state = State.DEAD

    # ── награда за смерть ─────────────────────────────────────────────────────
    def on_death(self, player):
        player.gain_xp(SLIME_XP_REWARD)
        # Взвешенный лут через таблицу из core/loot.py
        item = roll_loot(SLIME_LOOT_TABLE)
        if item == "slime_goo":
            player.inventory.add_item("slime_goo", random.randint(1, 2))

    # ── визуальный update (bounce, squash) перед FSM ──────────────────────────
    def _update_visuals(self, dt_sec: float, dt: float):
        self._hit_flash = max(0.0, self._hit_flash - dt_sec)
        if self.state in (State.APPROACH, State.WANDER):
            self._bounce_phase += 5.0 * dt_sec
        elif self.state == State.LUNGE:
            self._squash = max(0.6, self._squash - 0.08 * dt)

    # ── реализация FSM (требуется Enemy) ─────────────────────────────────────
    def _run_state_machine(self, player, dt_sec: float, dt: float,
                           pdx: float, pdy: float, dist: float):
        self._update_visuals(dt_sec, dt)

        if self.state == State.STUNNED:
            self._do_stunned(dt_sec)
        elif self.state == State.WANDER:
            self._do_wander(dt_sec, dt, dist)
        elif self.state == State.APPROACH:
            self._do_approach(dt, pdx, pdy, dist)
        elif self.state == State.PREPARE:
            self._do_prepare(dt_sec, pdx, pdy, dist)
        elif self.state == State.LUNGE:
            self._do_lunge(dt, dt_sec, dist)
        elif self.state == State.ATTACK:
            self._do_attack(dt_sec, pdx, pdy, dist, player)
        elif self.state == State.RECOIL:
            self._do_recoil(dt, dt_sec, dist)

    # ── состояния ─────────────────────────────────────────────────────────────
    def _do_stunned(self, dt_sec: float):
        self.vx *= 0.72
        self.vy *= 0.72
        if self._state_timer >= STUN_TIME:
            self._enter(State.APPROACH)

    def _do_wander(self, dt_sec: float, dt: float, dist: float):
        self._wander_timer -= dt_sec
        if self._wander_timer <= 0:
            a = random.uniform(0, math.pi * 2)
            self._wander_dx = math.cos(a)
            self._wander_dy = math.sin(a)
            self._wander_timer = random.uniform(1.0, 2.5)

        ws = self.speed * 0.45
        self.vx = self._wander_dx * ws
        self.vy = self._wander_dy * ws

        if dist < DETECT_RANGE:
            self._enter(State.APPROACH)

    def _do_approach(self, dt: float, pdx: float, pdy: float, dist: float):
        if dist > DETECT_RANGE * 1.3:
            self._enter(State.WANDER)
            return
        if dist <= PREPARE_RANGE:
            self.vx = 0
            self.vy = 0
            self._enter(State.PREPARE)
            return
        if dist > 0:
            base_angle = math.atan2(pdy, pdx)
            offset_rad = math.radians(self._orbit_offset)
            blend = max(0.0, (PREPARE_RANGE * 2 - dist) / (PREPARE_RANGE * 2))
            final_angle = base_angle + offset_rad * blend
            self.vx = math.cos(final_angle) * self.speed
            self.vy = math.sin(final_angle) * self.speed

    def _do_prepare(self, dt_sec: float, pdx: float, pdy: float, dist: float):
        self.vx *= 0.78
        self.vy *= 0.78
        if self._state_timer >= PREPARE_TIME:
            if dist > 0:
                nx, ny = pdx / dist, pdy / dist
            else:
                nx, ny = 1.0, 0.0
            self._lunge_tx = self.x + nx * dist * 1.1
            self._lunge_ty = self.y + ny * dist * 1.1
            self._squash = 1.35
            self._enter(State.LUNGE)

    def _do_lunge(self, dt: float, dt_sec: float, dist_to_player: float):
        ldx = self._lunge_tx - self.x
        ldy = self._lunge_ty - self.y
        d = math.hypot(ldx, ldy)
        if d > 0:
            self.vx = (ldx / d) * SLIME_LUNGE_SPEED
            self.vy = (ldy / d) * SLIME_LUNGE_SPEED
        else:
            self.vx = self.vy = 0
        if d < 12 or self._state_timer > 0.40:
            self.vx = self.vy = 0
            self._squash = 0.65
            if dist_to_player <= ATTACK_RANGE:
                self._enter(State.ATTACK)
            else:
                self._enter(State.RECOIL)

    def _do_attack(self, dt_sec: float, pdx: float, pdy: float,
                   dist: float, player):
        self.vx *= 0.82
        self.vy *= 0.82
        if dist > ATTACK_RANGE * 2.5:
            self._enter(State.APPROACH)
            return
        if self._attack_cd <= 0:
            player.take_damage(self.damage)
            self._attack_cd = SLIME_ATTACK_CD
            if dist > 0:
                self.vx = -(pdx / dist) * 2.0
                self.vy = -(pdy / dist) * 2.0

    def _do_recoil(self, dt: float, dt_sec: float, dist: float):
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


# ─── Менеджер слаймов ─────────────────────────────────────────────────────────
class SlimeManager(EnemyManager):
    """
    Специализированный менеджер для слаймов.
    Наследует EnemyManager — получает update(), apply_damage(), count бесплатно.
    Добавляет только spawn_wave() и spawn_one() для создания слаймов.
    """

    def spawn_wave(self, wave: int = 1, count: int = 5):
        """Заспавнить волну слаймов на краях карты."""
        for _ in range(count):
            x, y = self._edge_pos()
            self.add(Slime(x, y, wave=wave))

    def spawn_one(self, wave: int = 1):
        """Заспавнить одного слайма на краю карты."""
        x, y = self._edge_pos()
        self.add(Slime(x, y, wave=wave))

    # Псевдоним для обратной совместимости с main.py
    @property
    def slimes(self) -> list:
        return self.enemies

    def apply_damage_to_slimes(self, player):
        """Обратная совместимость — делегируем в apply_damage."""
        self.apply_damage(player)
