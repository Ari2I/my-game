"""
core/projectile.py — снаряды дальних врагов.

Принцип SRP: Projectile отвечает только за физику полёта и проверку границ.
Отрисовка — в core/render/projectile_renderer.py.
"""

import math


# ─── Константы снаряда ────────────────────────────────────────────────────────
PROJECTILE_RADIUS   = 6      # визуальный радиус, пикселей
PROJECTILE_LIFETIME = 4.0    # максимальное время жизни, секунд


class Projectile:
    """
    Летящий снаряд, движущийся по прямой.

    Деактивируется при:
      - выходе за границы карты
      - попадании в стену (wall_map.is_solid_point)
      - истечении времени жизни (PROJECTILE_LIFETIME)
      - попадании в игрока (обрабатывается снаружи в main.py)
    """

    RADIUS = PROJECTILE_RADIUS

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 damage: float, owner_wave: int = 1):
        self.x      = float(x)
        self.y      = float(y)
        self.vx     = float(vx)
        self.vy     = float(vy)
        self.damage = float(damage)
        self.alive  = True
        self.wave   = owner_wave

        self._lifetime: float = 0.0

    def update(self, dt: float, map_w: int, map_h: int,
               wall_map=None) -> None:
        """
        Обновляет позицию снаряда.

        Args:
            dt:       дельта времени в «тиках» (как везде по проекту: 60 = 1 сек)
            map_w:    ширина карты в пикселях
            map_h:    высота карты в пикселях
            wall_map: WallMap для проверки коллизий со стенами (опционально)
        """
        if not self.alive:
            return

        dt_sec = dt / 60.0
        self._lifetime += dt_sec

        # Время жизни истекло
        if self._lifetime >= PROJECTILE_LIFETIME:
            self.alive = False
            return

        self.x += self.vx * dt
        self.y += self.vy * dt

        # Выход за границы карты
        if (self.x < 0 or self.x > map_w or
                self.y < 0 or self.y > map_h):
            self.alive = False
            return

        # Коллизия со стеной
        if wall_map is not None and wall_map.is_solid_point(self.x, self.y):
            self.alive = False

    def hits_player(self, player) -> bool:
        """
        Проверяет попадание снаряда в хитбокс игрока.
        Использует расстояние от центра хитбокса.
        """
        if not self.alive:
            return False
        px = player.hitbox.centerx
        py = player.hitbox.centery
        dist = math.hypot(self.x - px, self.y - py)
        # Радиус хитбокса игрока ≈ половина диагонали (14px)
        return dist <= self.RADIUS + 14