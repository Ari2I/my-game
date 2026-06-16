import pygame
import math

# ─── Константы прокачки ───────────────────────────────────────────────────────
BASE_HP       = 100
BASE_SPEED    = 5
BASE_DAMAGE   = 15
XP_PER_LEVEL  = 100

STAT_POINTS_PER_LEVEL = 3
HP_PER_POINT     = 20
SPEED_PER_POINT  = 0.4
DAMAGE_PER_POINT = 8

# ─── Параметры атаки ──────────────────────────────────────────────────────────
ATTACK_CONE_ANGLE  = 80.0
ATTACK_CONE_RADIUS = 110
ATTACK_COOLDOWN    = 0.55
IFRAME_DURATION    = 0.65

# ─── Хитбокс ──────────────────────────────────────────────────────────────────
HITBOX_W        = 28
HITBOX_H        = 28
# Смещение хитбокса вниз от world_x/y (центра спрайта).
# Меняй только это число — хитбокс сдвинется к ногам.
HITBOX_OFFSET_Y = 30

FACING_ANGLES = {
    "right": 0.0,
    "down":  90.0,
    "left":  180.0,
    "up":    270.0,
}


class Stats:
    def __init__(self):
        self.vitality    = 0
        self.power       = 0
        self.agility     = 0
        self.free_points = 0

    def max_hp(self):
        return BASE_HP + self.vitality * HP_PER_POINT

    def speed(self):
        return BASE_SPEED + self.agility * SPEED_PER_POINT

    def damage(self):
        return BASE_DAMAGE + self.power * DAMAGE_PER_POINT

    def add_point(self, stat: str):
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

    def to_dict(self):
        return {"vitality": self.vitality, "power": self.power,
                "agility": self.agility, "free_points": self.free_points}

    def from_dict(self, d):
        self.vitality    = d.get("vitality",    0)
        self.power       = d.get("power",       0)
        self.agility     = d.get("agility",     0)
        self.free_points = d.get("free_points", 0)


class Inventory:
    def __init__(self):
        self.slime_goo = 0

    def to_dict(self):
        return {"slime_goo": self.slime_goo}

    def from_dict(self, d):
        self.slime_goo = d.get("slime_goo", 0)


class Player:
    def __init__(self, x, y):
        self.sprite_sheet = pygame.image.load(
            "images/character-spritesheet.png").convert_alpha()

        self.animations = {
            "walk": {
                "down":  self._load(640,  64,  64, 9, 2),
                "left":  self._load(576,  64,  64, 9, 2),
                "right": self._load(704,  64,  64, 9, 2),
                "up":    self._load(512,  64,  64, 9, 2),
                "speed": 0.5,
            },
            "attack": {
                "down":  self._load(3840, 192, 192, 6, 2),
                "up":    self._load(3456, 192, 192, 6, 2),
                "left":  self._load(3648, 192, 192, 6, 2),
                "right": self._load(4032, 192, 192, 6, 2),
                "speed": 0.5,
            },
            "idle": {
                "down":  self._load(1536, 64, 64, 2, 2),
                "left":  self._load(1472, 64, 64, 2, 2),
                "up":    self._load(1408, 64, 64, 2, 2),
                "right": self._load(1600, 64, 64, 2, 2),
                "speed": 0.15,
            },
        }

        self.state        = "idle"
        self.facing       = "down"
        self.frame_index  = 0.0
        self.is_attacking = False

        # ── Мировые координаты (центр спрайта) ───────────────────────────────
        # Единственный источник истины о позиции персонажа.
        # Движение и коллизии работают только через эти два числа.
        self.world_x = float(x)
        self.world_y = float(y)

        # ── Визуальный rect (меняет размер со спрайтом, только для отрисовки) ─
        self.image = self.animations["idle"]["down"][0]
        self.rect  = self.image.get_rect(center=(x, y))

        # ── Хитбокс (фиксированный размер, для коллизий со стенами и врагами) ─
        self.hitbox = pygame.Rect(0, 0, HITBOX_W, HITBOX_H)
        self._sync_rects()

        self.stats     = Stats()
        self.inventory = Inventory()
        self.level = 1
        self.xp    = 0

        self._current_hp: float = float(self.stats.max_hp())
        self._attack_cd:  float = 0.0
        self._iframe_cd:  float = 0.0
        self._hit_dealt:  bool  = False

    # ── синхронизация rect и hitbox из world_x/y ─────────────────────────────
    def _sync_rects(self):
        """Пересчитывает hitbox и rect из world_x/world_y.
        Вызывается после любого изменения позиции."""
        self.hitbox.center = (int(self.world_x),
                              int(self.world_y) + HITBOX_OFFSET_Y)
        self.rect.center   = (int(self.world_x), int(self.world_y))

    # ── загрузка кадров ───────────────────────────────────────────────────────
    def _load(self, y, fw, fh, count, scale=1):
        frames = []
        for i in range(count):
            f = self.sprite_sheet.subsurface((i * fw, y, fw, fh))
            if scale != 1:
                f = pygame.transform.scale(f, (fw * scale, fh * scale))
            frames.append(f)
        return frames

    def load_animations(self, sheet, curr_y, frame_w, frame_h, frame_count, scale=1):
        return self._load(curr_y, frame_w, frame_h, frame_count, scale)

    # ── HP ────────────────────────────────────────────────────────────────────
    @property
    def current_hp(self):
        return self._current_hp

    @current_hp.setter
    def current_hp(self, value):
        self._current_hp = max(0.0, min(float(value), float(self.stats.max_hp())))

    # ── опыт ─────────────────────────────────────────────────────────────────
    def gain_xp(self, amount: int):
        self.xp += amount
        needed = XP_PER_LEVEL * self.level
        while self.xp >= needed:
            self.xp   -= needed
            self.level += 1
            self.stats.free_points += STAT_POINTS_PER_LEVEL
            self._current_hp = float(self.stats.max_hp())
            needed = XP_PER_LEVEL * self.level

    def xp_to_next(self):
        return XP_PER_LEVEL * self.level

    # ── получение урона с i-frames ────────────────────────────────────────────
    def take_damage(self, amount: float):
        if self._iframe_cd > 0:
            return
        self.current_hp -= amount
        self._iframe_cd = IFRAME_DURATION

    @property
    def is_invincible(self):
        return self._iframe_cd > 0

    # ── конус атаки ───────────────────────────────────────────────────────────
    def get_attack_cone(self):
        """Начало конуса — от хитбокса (реальная позиция ног), не от центра спрайта."""
        cx = float(self.hitbox.centerx)
        cy = float(self.hitbox.centery)
        angle = FACING_ANGLES[self.facing]
        rad = math.radians(angle)
        ox  = cx + math.cos(rad) * 20
        oy  = cy + math.sin(rad) * 20
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
    def try_deal_attack(self, slime_manager) -> bool:
        if not self.is_attacking:
            return False
        if self._attack_cd > 0:
            return False
        if self._hit_dealt:
            return False

        total = len(self.animations["attack"][self.facing])
        progress = self.frame_index / total
        if not (0.30 <= progress <= 0.70):
            return False

        dmg = self.stats.damage()
        hit_any = False
        for slime in slime_manager.slimes:
            if self.point_in_attack_cone(slime.x, slime.y):
                slime.take_damage(dmg)
                hit_any = True

        if hit_any or progress >= 0.30:
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
            self.state        = "attack"
            self.is_attacking = True
            self.frame_index  = 0.0
            self._hit_dealt   = False
            moving = True
        else:
            if keys[pygame.K_w]:
                self.world_y -= spd; self.facing = "up";    moving = True
            elif keys[pygame.K_s]:
                self.world_y += spd; self.facing = "down";  moving = True
            if keys[pygame.K_a]:
                self.world_x -= spd; self.facing = "left";  moving = True
            elif keys[pygame.K_d]:
                self.world_x += spd; self.facing = "right"; moving = True

        if not moving:
            self.state = "idle"

        # Синхронизируем rect и hitbox после изменения world_x/y
        self._sync_rects()
        self.animate(dt)

    def animate(self, dt: float = 1.0):
        anim   = self.animations[self.state]
        frames = anim[self.facing]
        self.frame_index += anim["speed"] * dt

        if self.frame_index >= len(frames):
            self.frame_index = 0.0
            if self.is_attacking:
                self.is_attacking = False
                self._hit_dealt   = False
                self.state = "idle"

        # rect меняет размер под спрайт, но центрируется по world_x/y
        self.image = frames[int(self.frame_index)]
        self.rect  = self.image.get_rect(center=(int(self.world_x), int(self.world_y)))
        # hitbox не меняется — просто переставляем на место
        self.hitbox.center = (int(self.world_x),
                              int(self.world_y) + HITBOX_OFFSET_Y)

    # ── сериализация ──────────────────────────────────────────────────────────
    def to_dict(self):
        return {"x": self.world_x, "y": self.world_y,
                "level": self.level, "xp": self.xp,
                "current_hp": self._current_hp,
                "stats": self.stats.to_dict(),
                "inventory": self.inventory.to_dict()}

    def from_dict(self, d):
        self.world_x = float(d.get("x", self.world_x))
        self.world_y = float(d.get("y", self.world_y))
        self._sync_rects()
        self.level = d.get("level", 1)
        self.xp    = d.get("xp",    0)
        self.stats.from_dict(d.get("stats", {}))
        self.inventory.from_dict(d.get("inventory", {}))
        self._current_hp = d.get("current_hp", float(self.stats.max_hp()))