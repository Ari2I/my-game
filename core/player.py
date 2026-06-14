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
ATTACK_CONE_ANGLE  = 80.0   # полуугол конуса в градусах (итого 160°)
ATTACK_CONE_RADIUS = 110    # дальность удара в пикселях
ATTACK_COOLDOWN    = 0.55   # сек между ударами игрока
IFRAME_DURATION    = 0.65   # сек неуязвимости после получения урона (i-frames)

# ─── Коллизионный хитбокс игрока ───────────────────────────────────────────────
# Размер НЕ зависит от размера кадров анимации (idle/walk — 64x64, attack — 192x192).
# Должен быть меньше тайла стены (64x64), чтобы персонаж не цеплялся за края.
PLAYER_HITBOX_W = 36
PLAYER_HITBOX_H = 50

# Углы направлений (в градусах, от оси X вправо)
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

        self.image = self.animations["idle"]["down"][0]

        # ── хитбокс игрока (фиксированный размер, не зависит от кадра анимации)
        self.rect = pygame.Rect(0, 0, PLAYER_HITBOX_W, PLAYER_HITBOX_H)
        self.rect.center = (x, y)

        self.stats     = Stats()
        self.inventory = Inventory()
        self.level = 1
        self.xp    = 0

        self._current_hp: float = float(self.stats.max_hp())

        # ── кулдаун атаки и i-frames ──────────────────────────────────────────
        self._attack_cd:   float = 0.0   # сек до следующей атаки
        self._iframe_cd:   float = 0.0   # сек неуязвимости
        # флаг: удар уже нанесён в текущей анимации атаки
        self._hit_dealt: bool = False

    # ── загрузка кадров ───────────────────────────────────────────────────────
    def _load(self, y, fw, fh, count, scale=1):
        frames = []
        for i in range(count):
            f = self.sprite_sheet.subsurface((i * fw, y, fw, fh))
            if scale != 1:
                f = pygame.transform.scale(f, (fw * scale, fh * scale))
            frames.append(f)
        return frames

    # совместимость с предыдущим кодом
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
            return   # неуязвима
        self.current_hp -= amount
        self._iframe_cd = IFRAME_DURATION

    @property
    def is_invincible(self):
        return self._iframe_cd > 0

    # ── конус атаки ───────────────────────────────────────────────────────────
    def get_attack_cone(self):
        """
        Возвращает (origin_x, origin_y, direction_angle_deg, half_angle_deg, radius).
        origin — центр игрока, немного сдвинутый в сторону атаки.
        """
        cx, cy = self.rect.centerx, self.rect.centery
        angle  = FACING_ANGLES[self.facing]
        # сдвиг начала конуса чуть вперёд
        rad = math.radians(angle)
        ox  = cx + math.cos(rad) * 20
        oy  = cy + math.sin(rad) * 20
        return ox, oy, angle, ATTACK_CONE_ANGLE, ATTACK_CONE_RADIUS

    def point_in_attack_cone(self, px: float, py: float) -> bool:
        """True, если точка (px, py) попадает в конус атаки."""
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

    # ── нанесение удара (вызывается из main в нужный момент анимации) ─────────
    def try_deal_attack(self, slime_manager) -> bool:
        """
        Проверяет: идёт ли анимация атаки, не истёк ли кд, не был ли удар
        уже нанесён в этой анимации. Если всё ок — бьёт слаймов в конусе.
        Возвращает True, если удар был нанесён.
        """
        if not self.is_attacking:
            return False
        if self._attack_cd > 0:
            return False
        if self._hit_dealt:
            return False

        # «активный» фрейм атаки: примерно 35–70% анимации
        total = len(self.animations["attack"][self.facing])
        progress = self.frame_index / total
        if not (0.30 <= progress <= 0.70):
            return False

        # наносим урон
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

        if self._attack_cd  > 0: self._attack_cd  = max(0.0, self._attack_cd  - dt_sec)
        if self._iframe_cd  > 0: self._iframe_cd  = max(0.0, self._iframe_cd  - dt_sec)

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
                self.rect.y -= spd; self.facing = "up";    moving = True
            elif keys[pygame.K_s]:
                self.rect.y += spd; self.facing = "down";  moving = True
            if keys[pygame.K_a]:
                self.rect.x -= spd; self.facing = "left";  moving = True
            elif keys[pygame.K_d]:
                self.rect.x += spd; self.facing = "right"; moving = True

        if not moving:
            self.state = "idle"

        self.animate(dt)

    def animate(self, dt: float = 1.0):
        anim  = self.animations[self.state]
        frames = anim[self.facing]
        self.frame_index += anim["speed"] * dt
        if self.frame_index >= len(frames):
            self.frame_index = 0.0
            if self.is_attacking:
                self.is_attacking = False
                self._hit_dealt   = False
                self.state = "idle"
        # ВАЖНО: self.rect — это коллизионный хитбокс фиксированного размера,
        # его размер/позиция НЕ пересчитываются по размеру кадра анимации.
        self.image = frames[int(self.frame_index)]

    def draw(self, screen, camera_x=0, camera_y=0):
        # картинка может быть крупнее хитбокса (например, кадры атаки 192x192) —
        # центрируем её относительно хитбокса для отрисовки
        img_rect = self.image.get_rect(center=self.rect.center)
        screen.blit(self.image, (img_rect.x - camera_x, img_rect.y - camera_y))

    # ── отладочная отрисовка конуса ───────────────────────────────────────────
    def draw_attack_cone(self, screen, camera_x=0, camera_y=0):
        """Рисует конус атаки (для отладки, вызвать до pygame.display.flip)."""
        if not self.is_attacking:
            return
        ox, oy, dir_deg, half_deg, radius = self.get_attack_cone()
        sx, sy = int(ox) - camera_x, int(oy) - camera_y

        cone_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        # рисуем сектор полигоном
        steps   = 20
        start_a = math.radians(dir_deg - half_deg)
        end_a   = math.radians(dir_deg + half_deg)
        cx_s    = radius + 2
        cy_s    = radius + 2
        points  = [(cx_s, cy_s)]
        for i in range(steps + 1):
            a = start_a + (end_a - start_a) * i / steps
            points.append((cx_s + math.cos(a) * radius, cy_s + math.sin(a) * radius))
        pygame.draw.polygon(cone_surf, (255, 220, 50, 55), points)
        pygame.draw.polygon(cone_surf, (255, 220, 50, 130), points, width=2)
        screen.blit(cone_surf, (sx - radius - 2, sy - radius - 2))

    # ── сериализация ──────────────────────────────────────────────────────────
    def to_dict(self):
        return {"x": self.rect.centerx, "y": self.rect.centery,
                "level": self.level, "xp": self.xp,
                "current_hp": self._current_hp,
                "stats": self.stats.to_dict(),
                "inventory": self.inventory.to_dict()}

    def from_dict(self, d):
        self.rect.center = (d.get("x", self.rect.centerx),
                            d.get("y", self.rect.centery))
        self.level = d.get("level", 1)
        self.xp    = d.get("xp",    0)
        self.stats.from_dict(d.get("stats", {}))
        self.inventory.from_dict(d.get("inventory", {}))
        self._current_hp = d.get("current_hp", float(self.stats.max_hp()))