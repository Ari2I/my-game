"""
core/ranged_enemy.py — дальний враг «Теневой лучник».

Логика ИИ принципиально отличается от слайма:
  - Держит дистанцию (не подходит ближе MIN_DISTANCE)
  - Отступает, если игрок подходит слишком близко
  - Периодически стреляет снарядами (создаёт объект Projectile)
  - Не делает бросок (LUNGE) — уклоняется боковым движением

FSM состояния:
  PATROL → REPOSITION → AIM → SHOOT → FLEE → STUNNED

Наследует Enemy — получает take_damage, _enter, _separate, update() бесплатно.
"""

import math
import random
import pygame

from core.enemy      import Enemy, EnemyManager
from core.projectile import Projectile
from core.loot       import roll_loot, RANGED_ENEMY_LOOT_TABLE


# ─── Константы дальнего врага ─────────────────────────────────────────────────
RANGED_BASE_HP        = 45
RANGED_BASE_SPEED     = 1.1
RANGED_BASE_DAMAGE    = 8       # урон снаряда
RANGED_XP_REWARD      = 40

MIN_DISTANCE          = 200     # минимальная дистанция до игрока (отступает если ближе)
IDEAL_DISTANCE        = 320     # идеальная дистанция для стрельбы
MAX_DISTANCE          = 480     # дальше этого — начинает сближаться

SHOOT_COOLDOWN        = 2.2     # секунд между выстрелами
AIM_TIME              = 0.6     # секунд прицеливания перед выстрелом
STUN_TIME             = 0.4     # секунд оглушения
FLEE_TIME             = 0.8     # секунд бегства при слишком близком игроке

PROJECTILE_SPEED      = 4.5     # скорость снаряда (в тиках)
STRAFE_AMPLITUDE      = 1.0     # амплитуда бокового движения при REPOSITION


class RangedState:
    PATROL      = "patrol"      # медленное патрулирование на краях карты
    REPOSITION  = "reposition"  # движение к идеальной дистанции
    AIM         = "aim"         # прицеливание (короткая остановка)
    SHOOT       = "shoot"       # выстрел
    FLEE        = "flee"        # бегство если игрок слишком близко
    STUNNED     = "stunned"     # оглушение после удара
    DEAD        = "dead"


class RangedEnemy(Enemy):
    """
    Дальний враг. Стреляет снарядами и держит дистанцию.

    Отличия от Slime:
      - Не использует LUNGE и ATTACK в упор
      - Создаёт Projectile объекты (записывает в self.projectiles)
      - Боковое маневрирование при REPOSITION
      - FLEE при вторжении игрока в MIN_DISTANCE
    """

    HITBOX_SIZE = 36

    def __init__(self, x: float, y: float, wave: int = 1):
        scale = 1.0 + (wave - 1) * 0.2

        super().__init__(
            x=x, y=y, wave=wave,
            max_hp=RANGED_BASE_HP   * scale,
            speed =RANGED_BASE_SPEED * (1.0 + (wave - 1) * 0.06),
            damage=RANGED_BASE_DAMAGE * scale,
        )

        self._enter(RangedState.PATROL)
        self._attack_cd = random.uniform(0, SHOOT_COOLDOWN)

        # Направление патруля
        angle              = random.uniform(0, math.pi * 2)
        self._patrol_dx    = math.cos(angle)
        self._patrol_dy    = math.sin(angle)
        self._patrol_timer = random.uniform(1.0, 3.0)

        # Боковое маневрирование (strafe)
        self._strafe_dir   = random.choice([-1, 1])
        self._strafe_timer = 0.0

        # Список снарядов — заполняется при выстреле, читается main.py
        self.projectiles: list[Projectile] = []

        # Визуал
        self._hit_flash    = 0.0
        self._aim_progress = 0.0   # [0..1], для рендерера (анимация прицела)

    # ── публичные свойства для рендерера ─────────────────────────────────────
    @property
    def hit_flash(self) -> float:
        return self._hit_flash

    @property
    def aim_progress(self) -> float:
        return self._aim_progress

    @property
    def state_timer(self) -> float:
        return self._state_timer

    # ── переопределяем take_damage: добавляем стан и вспышку ─────────────────
    def take_damage(self, amount: float):
        if not self.alive:
            return
        self.hp -= amount
        self._hit_flash = 0.15
        if self.state not in (RangedState.DEAD, RangedState.STUNNED):
            self._enter(RangedState.STUNNED)
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
            self.state = RangedState.DEAD

    # ── награда за смерть ─────────────────────────────────────────────────────
    def on_death(self, player):
        player.gain_xp(RANGED_XP_REWARD)
        item = roll_loot(RANGED_ENEMY_LOOT_TABLE)
        if item in ("magic_shard", "rune_stone"):
            player.inventory.add_item(item, 1)

    # ── FSM ──────────────────────────────────────────────────────────────────
    def _run_state_machine(self, player, dt_sec: float, dt: float,
                           pdx: float, pdy: float, dist: float):
        self._hit_flash = max(0.0, self._hit_flash - dt_sec)
        self._attack_cd = max(0.0, self._attack_cd - dt_sec)

        if   self.state == RangedState.STUNNED:    self._do_stunned(dt_sec, dist)
        elif self.state == RangedState.FLEE:        self._do_flee(dt, dt_sec, pdx, pdy, dist)
        elif self.state == RangedState.PATROL:      self._do_patrol(dt_sec, dist)
        elif self.state == RangedState.REPOSITION:  self._do_reposition(dt, dt_sec, pdx, pdy, dist)
        elif self.state == RangedState.AIM:         self._do_aim(dt_sec, pdx, pdy, dist, player)
        elif self.state == RangedState.SHOOT:       self._do_shoot(pdx, pdy, dist)

    def _do_stunned(self, dt_sec: float, dist: float):
        self.vx *= 0.70
        self.vy *= 0.70
        self._aim_progress = 0.0
        if self._state_timer >= STUN_TIME:
            self._enter(RangedState.REPOSITION if dist < MAX_DISTANCE
                        else RangedState.PATROL)

    def _do_flee(self, dt: float, dt_sec: float,
                 pdx: float, pdy: float, dist: float):
        """Бегство от игрока при слишком близком расстоянии."""
        if dist > 0:
            # Убегаем прямо от игрока
            self.vx = -(pdx / dist) * self.speed * 1.5
            self.vy = -(pdy / dist) * self.speed * 1.5
        if self._state_timer >= FLEE_TIME or dist > MIN_DISTANCE:
            self._enter(RangedState.REPOSITION)

    def _do_patrol(self, dt_sec: float, dist: float):
        """Медленное патрулирование, пока игрок далеко."""
        self._patrol_timer -= dt_sec
        if self._patrol_timer <= 0:
            import random
            a = random.uniform(0, math.pi * 2)
            self._patrol_dx    = math.cos(a)
            self._patrol_dy    = math.sin(a)
            self._patrol_timer = random.uniform(1.5, 3.5)

        self.vx = self._patrol_dx * self.speed * 0.4
        self.vy = self._patrol_dy * self.speed * 0.4

        if dist < MAX_DISTANCE:
            self._enter(RangedState.REPOSITION)

    def _do_reposition(self, dt: float, dt_sec: float,
                       pdx: float, pdy: float, dist: float):
        """
        Движение к идеальной позиции + боковое маневрирование.
        Держит дистанцию IDEAL_DISTANCE от игрока.
        """
        if dist < MIN_DISTANCE:
            self._enter(RangedState.FLEE)
            return

        if dist > 0:
            # Продольная компонента: двигаемся к/от игрока
            if dist < IDEAL_DISTANCE - 20:
                # Слишком близко — отступаем
                longitudinal = -1.0
            elif dist > IDEAL_DISTANCE + 20:
                # Слишком далеко — сближаемся
                longitudinal = 1.0
            else:
                longitudinal = 0.0

            nx, ny = pdx / dist, pdy / dist

            # Боковая компонента: strafe (перпендикуляр к вектору на игрока)
            self._strafe_timer += dt_sec
            if self._strafe_timer > 2.0:
                self._strafe_dir   = -self._strafe_dir
                self._strafe_timer = 0.0

            # Перпендикуляр: (-ny, nx) или (ny, -nx)
            perp_x = -ny * self._strafe_dir
            perp_y =  nx * self._strafe_dir

            spd = self.speed
            self.vx = (nx * longitudinal * spd + perp_x * STRAFE_AMPLITUDE * spd)
            self.vy = (ny * longitudinal * spd + perp_y * STRAFE_AMPLITUDE * spd)

        # Готов стрелять?
        if (IDEAL_DISTANCE - 60 <= dist <= IDEAL_DISTANCE + 80
                and self._attack_cd <= 0):
            self.vx = 0
            self.vy = 0
            self._aim_progress = 0.0
            self._enter(RangedState.AIM)

    def _do_aim(self, dt_sec: float, pdx: float, pdy: float,
                dist: float, player):
        """Короткая остановка перед выстрелом."""
        self.vx *= 0.85
        self.vy *= 0.85
        self._aim_progress = min(1.0, self._state_timer / AIM_TIME)

        if dist < MIN_DISTANCE:
            self._aim_progress = 0.0
            self._enter(RangedState.FLEE)
            return

        if self._state_timer >= AIM_TIME:
            self._fire(pdx, pdy, dist)
            self._aim_progress = 0.0
            self._enter(RangedState.SHOOT)

    def _do_shoot(self, pdx: float, pdy: float, dist: float):
        """Кадр после выстрела — сразу переходим к репозиционированию."""
        self._enter(RangedState.REPOSITION)
        self._attack_cd = SHOOT_COOLDOWN

    def _fire(self, pdx: float, pdy: float, dist: float):
        """Создаёт снаряд, направленный в игрока."""
        if dist < 1e-3:
            return
        nx = pdx / dist
        ny = pdy / dist
        # Небольшой разброс ±5°
        spread = math.radians(random.uniform(-5, 5))
        cos_s, sin_s = math.cos(spread), math.sin(spread)
        vx = (nx * cos_s - ny * sin_s) * PROJECTILE_SPEED
        vy = (nx * sin_s + ny * cos_s) * PROJECTILE_SPEED

        self.projectiles.append(
            Projectile(self.x, self.y, vx, vy, self.damage, self.wave)
        )


# ─── Менеджер дальних врагов ──────────────────────────────────────────────────
class RangedEnemyManager(EnemyManager):
    """
    Менеджер дальних врагов. Дополнительно собирает все снаряды
    из RangedEnemy.projectiles и обновляет их.
    """

    def __init__(self, map_w: int, map_h: int):
        super().__init__(map_w, map_h)
        self.projectiles: list[Projectile] = []

    def spawn_wave(self, wave: int = 1, count: int = 3):
        """Заспавнить волну дальних врагов."""
        for _ in range(count):
            x, y = self._edge_pos()
            self.add(RangedEnemy(x, y, wave=wave))

    def spawn_one(self, wave: int = 1):
        x, y = self._edge_pos()
        self.add(RangedEnemy(x, y, wave=wave))

    def update(self, player, dt: float, wall_map=None):
        """Обновляет врагов и собирает/обновляет снаряды."""
        super().update(player, dt)

        # Собираем новые снаряды от всех врагов
        for e in self.enemies:
            if isinstance(e, RangedEnemy) and e.projectiles:
                self.projectiles.extend(e.projectiles)
                e.projectiles.clear()

        # Обновляем снаряды
        for p in self.projectiles:
            p.update(dt, self.map_w, self.map_h, wall_map)
            if p.alive and p.hits_player(player):
                player.take_damage(p.damage)
                p.alive = False

        self.projectiles = [p for p in self.projectiles if p.alive]

    @property
    def ranged_enemies(self) -> list:
        return self.enemies