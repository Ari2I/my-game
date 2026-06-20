"""
core/player.py — модель игрока (Model в паттерне MVC).

Принцип SRP: этот модуль отвечает только за данные и логику игрока.
Отрисовка вынесена в core/render/player_renderer.py.

Принцип DRY: все «магические числа» вынесены в именованные константы.
"""

import pygame
import math

# ─── Константы прокачки ───────────────────────────────────────────────────────
BASE_HP = 100
BASE_SPEED = 3
BASE_DAMAGE = 15
XP_PER_LEVEL = 100

STAT_POINTS_PER_LEVEL = 3
HP_PER_POINT = 20
SPEED_PER_POINT = 0.4
DAMAGE_PER_POINT = 8

# ─── Параметры атаки ──────────────────────────────────────────────────────────
ATTACK_CONE_ANGLE = 80.0  # полуугол конуса атаки, градусы
ATTACK_CONE_RADIUS = 110  # радиус конуса атаки, пикселей
ATTACK_COOLDOWN = 0.55  # секунд между атаками
IFRAME_DURATION = 0.65  # секунд неуязвимости после получения урона

# Прогресс анимации атаки [0..1], в котором засчитывается удар
ATTACK_HIT_START = 0.30
ATTACK_HIT_END = 0.70

# Смещение начала конуса атаки от центра хитбокса вперёд, пикселей
ATTACK_CONE_OFFSET = 20

# ─── Хитбокс ──────────────────────────────────────────────────────────────────
HITBOX_W = 52
HITBOX_H = 28
# Смещение хитбокса вниз от world_x/y (центра спрайта).
# Хитбокс намеренно маленький и привязан к ногам — нужен для коллизий со
# стенами (core/walls.py) и как точка приложения урона/атак, чтобы игрок
# не «застревал» и не останавливался раньше визуального контакта со стеной.
HITBOX_OFFSET_Y = 48

# ─── Раскладка спрайтшита ─────────────────────────────────────────────────────
# Формат: (y_offset, frame_w, frame_h, frame_count, scale)
SPRITE_SHEET_LAYOUT = {
    "walk": {
        "down": (640, 64, 64, 9, 2),
        "left": (576, 64, 64, 9, 2),
        "right": (704, 64, 64, 9, 2),
        "up": (512, 64, 64, 9, 2),
        "speed": 0.15,
    },
    "attack": {
        "down": (3840, 192, 192, 6, 2),
        "up": (3456, 192, 192, 6, 2),
        "left": (3648, 192, 192, 6, 2),
        "right": (4032, 192, 192, 6, 2),
        "speed": 0.25,
    },
    "idle": {
        "down": (1536, 64, 64, 2, 2),
        "left": (1472, 64, 64, 2, 2),
        "up": (1408, 64, 64, 2, 2),
        "right": (1600, 64, 64, 2, 2),
        "speed": 0.04,
    },
}

# ─── Углы направлений ─────────────────────────────────────────────────────────
FACING_ANGLES: dict[str, float] = {
    "right": 0.0,
    "down": 90.0,
    "left": 180.0,
    "up": 270.0,
}


class Stats:
    """Характеристики персонажа. Чистая модель без pygame."""

    def __init__(self):
        self.vitality: int = 0
        self.power: int = 0
        self.agility: int = 0
        self.free_points: int = 0

    def max_hp(self) -> int:
        return BASE_HP + self.vitality * HP_PER_POINT

    def speed(self) -> float:
        return BASE_SPEED + self.agility * SPEED_PER_POINT

    def damage(self) -> int:
        return BASE_DAMAGE + self.power * DAMAGE_PER_POINT

    def add_point(self, stat: str) -> bool:
        if self.free_points <= 0:
            return False
        if stat == "vitality":
            self.vitality += 1
        elif stat == "power":
            self.power += 1
        elif stat == "agility":
            self.agility += 1
        else:
            return False
        self.free_points -= 1
        return True

    def to_dict(self) -> dict:
        return {
            "vitality": self.vitality,
            "power": self.power,
            "agility": self.agility,
            "free_points": self.free_points,
        }

    def from_dict(self, d: dict):
        self.vitality = d.get("vitality", 0)
        self.power = d.get("power", 0)
        self.agility = d.get("agility", 0)
        self.free_points = d.get("free_points", 0)


class Inventory:
    """Инвентарь игрока. Хранит предметы в словаре items."""

    def __init__(self):
        # Словарь предметов: {название: количество}
        # Обратная совместимость: slime_goo доступен как свойство
        self.items: dict[str, int] = {}

    def add_item(self, name: str, amount: int = 1):
        """Добавить предмет в инвентарь."""
        self.items[name] = self.items.get(name, 0) + amount

    def get_item(self, name: str) -> int:
        """Получить количество предмета (0 если нет)."""
        return self.items.get(name, 0)

    # ── обратная совместимость с кодом, который обращается к slime_goo напрямую
    @property
    def slime_goo(self) -> int:
        return self.items.get("slime_goo", 0)

    @slime_goo.setter
    def slime_goo(self, value: int):
        self.items["slime_goo"] = value

    def to_dict(self) -> dict:
        return {"items": self.items.copy()}

    def from_dict(self, d: dict):
        # Поддержка старого формата (slime_goo напрямую)
        if "items" in d:
            self.items = d["items"].copy()
        elif "slime_goo" in d:
            self.items = {"slime_goo": d["slime_goo"]}
        else:
            self.items = {}


class Player:
    """
    Модель игрока: данные + логика + анимация.
    Отрисовка — в core/render/player_renderer.py (принцип SRP).

    Геометрия игрока представлена ДВУМЯ прямоугольниками с разным назначением:
      - hitbox     — маленький (HITBOX_W×HITBOX_H), привязан к ногам.
                     Используется для коллизий со стенами (core/walls.py),
                     приложения урона врагами и как опора для конуса атаки.
                     Намеренно компактный, чтобы игрок не «застревал» в стенах
                     раньше визуального контакта.
      - body_rect  — полный визуальный силуэт спрайта (alias на self.rect).
                     Используется ИСКЛЮЧИТЕЛЬНО для Y-сортировки отрисовки
                     (core/render/y_sort_renderer.py), чтобы «высокие» объекты
                     карты (деревья, постройки) корректно перекрывали игрока
                     целиком, а не только узкий хитбокс у ног — иначе голова
                     персонажа «торчит» из-под объекта, который должен
                     закрывать его полностью.
    """

    def __init__(self, x, y):
        self.sprite_sheet = pygame.image.load(
            "images/character-spritesheet.png").convert_alpha()

        # Загружаем анимации из раскладки спрайтшита
        self.animations: dict = {}
        for anim_name, anim_data in SPRITE_SHEET_LAYOUT.items():
            self.animations[anim_name] = {"speed": anim_data["speed"]}
            for direction in ("down", "left", "right", "up"):
                if direction in anim_data:
                    y_off, fw, fh, count, scale = anim_data[direction]
                    self.animations[anim_name][direction] = self._load(
                        y_off, fw, fh, count, scale)

        self.state = "idle"
        self.facing = "down"
        self.frame_index = 0.0
        self.is_attacking = False

        # ── Мировые координаты (центр спрайта) ───────────────────────────────
        self.world_x = float(x)
        self.world_y = float(y)

        # ── Визуальный rect (меняет размер со спрайтом, только для отрисовки
        #    и для Y-сортировки через свойство body_rect, см. докстринг класса) ─
        self.image = self.animations["idle"]["down"][0]
        self.rect = self.image.get_rect(center=(x, y))

        # ── Хитбокс (фиксированный размер, для коллизий со стенами и врагами) ─
        self.hitbox = pygame.Rect(0, 0, HITBOX_W, HITBOX_H)
        self._sync_rects()

        self.stats = Stats()
        self.inventory = Inventory()
        self.level = 1
        self.xp = 0

        self._current_hp: float = float(self.stats.max_hp())
        self._attack_cd: float = 0.0
        self._iframe_cd: float = 0.0
        self._hit_dealt: bool = False

    # ── синхронизация rect и hitbox из world_x/y ─────────────────────────────
    def _sync_rects(self):
        """Пересчитывает hitbox и rect из world_x/world_y."""
        self.hitbox.center = (int(self.world_x),
                              int(self.world_y) + HITBOX_OFFSET_Y)
        self.rect.center = (int(self.world_x), int(self.world_y))

    # ── публичный доступ к полному силуэту для Y-сортировки ──────────────────
    @property
    def body_rect(self) -> pygame.Rect:
        """
        Прямоугольник полного визуального силуэта спрайта.

        НЕ используется для коллизий со стенами и НЕ используется для
        получения/нанесения урона — для этого служит self.hitbox.
        Единственное назначение — Y-сортировка отрисовки
        (core/render/y_sort_renderer.py), чтобы объекты карты перекрывали
        игрока целиком (включая голову), а не только узкий хитбокс у ног.
        """
        return self.rect

    # ── загрузка кадров ───────────────────────────────────────────────────────
    def _load(self, y: int, fw: int, fh: int, count: int, scale: int = 1):
        frames = []
        for i in range(count):
            f = self.sprite_sheet.subsurface((i * fw, y, fw, fh))
            if scale != 1:
                f = pygame.transform.scale(f, (fw * scale, fh * scale))
            frames.append(f)
        return frames

    def load_animations(self, sheet, curr_y, frame_w, frame_h, frame_count, scale=1):
        """Публичный метод для загрузки анимаций вне конструктора."""
        return self._load(curr_y, frame_w, frame_h, frame_count, scale)

    # ── HP ────────────────────────────────────────────────────────────────────
    @property
    def current_hp(self) -> float:
        return self._current_hp

    @current_hp.setter
    def current_hp(self, value: float):
        self._current_hp = max(0.0, min(float(value), float(self.stats.max_hp())))

    # ── опыт ─────────────────────────────────────────────────────────────────
    def gain_xp(self, amount: int):
        self.xp += amount
        needed = XP_PER_LEVEL * self.level
        while self.xp >= needed:
            self.xp -= needed
            self.level += 1
            self.stats.free_points += STAT_POINTS_PER_LEVEL
            self._current_hp = float(self.stats.max_hp())
            needed = XP_PER_LEVEL * self.level

    def xp_to_next(self) -> int:
        return XP_PER_LEVEL * self.level

    # ── получение урона с i-frames ────────────────────────────────────────────
    def take_damage(self, amount: float):
        if self._iframe_cd > 0:
            return
        self.current_hp -= amount
        self._iframe_cd = IFRAME_DURATION

    @property
    def is_invincible(self) -> bool:
        return self._iframe_cd > 0

    # ── конус атаки ───────────────────────────────────────────────────────────
    def get_attack_cone(self) -> tuple:
        """Возвращает (ox, oy, angle, half_angle, radius)."""
        cx = float(self.hitbox.centerx)
        cy = float(self.hitbox.centery)
        angle = FACING_ANGLES[self.facing]
        rad = math.radians(angle)
        ox = cx + math.cos(rad) * ATTACK_CONE_OFFSET
        oy = cy + math.sin(rad) * ATTACK_CONE_OFFSET
        return ox, oy, angle, ATTACK_CONE_ANGLE, ATTACK_CONE_RADIUS

    def point_in_attack_cone(self, px: float, py: float) -> bool:
        ox, oy, dir_deg, half_deg, radius = self.get_attack_cone()
        dx, dy = px - ox, py - oy
        dist = math.hypot(dx, dy)
        if dist > radius or dist < 1e-3:
            return False
        point_angle = math.degrees(math.atan2(dy, dx)) % 360
        diff = abs(point_angle - dir_deg) % 360
        if diff > 180:
            diff = 360 - diff
        return diff <= half_deg

    # ── нанесение удара ───────────────────────────────────────────────────────
    def try_deal_attack(self, enemy_manager) -> bool:
        """
        Проверяет конус атаки и наносит урон врагам.
        Принимает любой EnemyManager (или совместимый объект).
        """
        if not self.is_attacking:
            return False
        if self._attack_cd > 0:
            return False
        if self._hit_dealt:
            return False

        total = len(self.animations["attack"][self.facing])
        progress = self.frame_index / total
        if not (ATTACK_HIT_START <= progress <= ATTACK_HIT_END):
            return False

        dmg = self.stats.damage()
        hit_any = False
        for enemy in enemy_manager.enemies:
            if self.point_in_attack_cone(enemy.x, enemy.y):
                enemy.take_damage(dmg)
                hit_any = True

        if hit_any or progress >= ATTACK_HIT_START:
            self._hit_dealt = True
            self._attack_cd = ATTACK_COOLDOWN

        return hit_any

    # ── обновление ───────────────────────────────────────────────────────────
    def update_player(self, keys, dt: float = 1.0):
        dt_sec = dt / 60.0

        if self._attack_cd > 0: self._attack_cd = max(0.0, self._attack_cd - dt_sec)
        if self._iframe_cd > 0: self._iframe_cd = max(0.0, self._iframe_cd - dt_sec)

        if self.is_attacking:
            self.animate(dt)
            return

        moving = False
        self.state = "walk"
        spd = self.stats.speed() * dt

        mouse = pygame.mouse.get_pressed()
        if mouse[0] and self._attack_cd <= 0:
            self.state = "attack"
            self.is_attacking = True
            self.frame_index = 0.0
            self._hit_dealt = False
            moving = True
        else:
            if keys[pygame.K_w]:
                self.world_y -= spd;
                self.facing = "up";
                moving = True
            elif keys[pygame.K_s]:
                self.world_y += spd;
                self.facing = "down";
                moving = True
            if keys[pygame.K_a]:
                self.world_x -= spd;
                self.facing = "left";
                moving = True
            elif keys[pygame.K_d]:
                self.world_x += spd;
                self.facing = "right";
                moving = True

        if not moving:
            self.state = "idle"

        self._sync_rects()
        self.animate(dt)

    def animate(self, dt: float = 1.0):
        anim = self.animations[self.state]
        frames = anim[self.facing]
        self.frame_index += anim["speed"] * dt

        if self.frame_index >= len(frames):
            self.frame_index = 0.0
            if self.is_attacking:
                self.is_attacking = False
                self._hit_dealt = False
                self.state = "idle"

        self.image = frames[int(self.frame_index)]
        self.rect = self.image.get_rect(center=(int(self.world_x), int(self.world_y)))
        self.hitbox.center = (int(self.world_x),
                              int(self.world_y) + HITBOX_OFFSET_Y)

    # ── сериализация ──────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "x": self.world_x,
            "y": self.world_y,
            "level": self.level,
            "xp": self.xp,
            "current_hp": self._current_hp,
            "stats": self.stats.to_dict(),
            "inventory": self.inventory.to_dict(),
        }

    def from_dict(self, d: dict):
        self.world_x = float(d.get("x", self.world_x))
        self.world_y = float(d.get("y", self.world_y))
        self._sync_rects()
        self.level = d.get("level", 1)
        self.xp = d.get("xp", 0)
        self.stats.from_dict(d.get("stats", {}))
        self.inventory.from_dict(d.get("inventory", {}))
        self._current_hp = d.get("current_hp", float(self.stats.max_hp()))