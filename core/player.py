import pygame
import math


# ─── Константы прокачки ───────────────────────────────────────────────────────
BASE_HP       = 100
BASE_SPEED    = 2.5
BASE_DAMAGE   = 15
XP_PER_LEVEL  = 100   # XP, нужный для следующего уровня (умножается на уровень)

# Очки характеристик за уровень
STAT_POINTS_PER_LEVEL = 3

# Бонусы за 1 очко вложенной характеристики
HP_PER_POINT      = 20    # +20 к макс. HP
SPEED_PER_POINT   = 0   # +0.4 к скорости
DAMAGE_PER_POINT  = 8     # +8 к урону


class Stats:
    """Характеристики персонажа (вложенные и рассчитанные)."""

    def __init__(self):
        # базовые вложения очков (растут при прокачке)
        self.vitality  = 0   # влияет на HP
        self.power     = 0   # влияет на урон
        self.agility   = 0   # влияет на скорость
        self.free_points = 0  # нераспределённые очки

    # ── расчётные значения ────────────────────────────────────────────────────
    def max_hp(self):
        return BASE_HP + self.vitality * HP_PER_POINT

    def speed(self):
        return BASE_SPEED + self.agility * SPEED_PER_POINT

    def damage(self):
        return BASE_DAMAGE + self.power * DAMAGE_PER_POINT

    def add_point(self, stat: str):
        """Вложить одно очко в stat. Возвращает True при успехе."""
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
        return {
            "vitality":    self.vitality,
            "power":       self.power,
            "agility":     self.agility,
            "free_points": self.free_points,
        }

    def from_dict(self, d):
        self.vitality    = d.get("vitality",    0)
        self.power       = d.get("power",       0)
        self.agility     = d.get("agility",     0)
        self.free_points = d.get("free_points", 0)


class Inventory:
    """Хранит ресурсы (слизь слаймов и др.)."""

    def __init__(self):
        self.slime_goo = 0   # слизь слаймов

    def to_dict(self):
        return {"slime_goo": self.slime_goo}

    def from_dict(self, d):
        self.slime_goo = d.get("slime_goo", 0)


class Player:
    """Игровой персонаж с анимацией, характеристиками и инвентарём."""

    def __init__(self, x, y):
        # ── спрайт ────────────────────────────────────────────────────────────
        self.sprite_sheet = pygame.image.load(
            "images/character-spritesheet.png").convert_alpha()

        self.frame_width  = 128
        self.frame_height = 128

        self.animations = {
            "walk": {
                "down":  self.load_animations(self.sprite_sheet, 640,  64,  64, 9, scale=2),
                "left":  self.load_animations(self.sprite_sheet, 576,  64,  64, 9, scale=2),
                "right": self.load_animations(self.sprite_sheet, 704,  64,  64, 9, scale=2),
                "up":    self.load_animations(self.sprite_sheet, 512,  64,  64, 9, scale=2),
                "speed": 0.1,
            },
            "attack": {
                "down":  self.load_animations(self.sprite_sheet, 3840, 192, 192, 6, scale=2),
                "up":    self.load_animations(self.sprite_sheet, 3456, 192, 192, 6, scale=2),
                "left":  self.load_animations(self.sprite_sheet, 3648, 192, 192, 6, scale=2),
                "right": self.load_animations(self.sprite_sheet, 4032, 192, 192, 6, scale=2),
                "speed": 0.1,
            },
            "idle": {
                "down":  self.load_animations(self.sprite_sheet, 1536, 64, 64, 2, scale=2),
                "left":  self.load_animations(self.sprite_sheet, 1472, 64, 64, 2, scale=2),
                "up":    self.load_animations(self.sprite_sheet, 1408, 64, 64, 2, scale=2),
                "right": self.load_animations(self.sprite_sheet, 1600, 64, 64, 2, scale=2),
                "speed": 0.025,
            },
        }

        self.state       = "idle"
        self.facing      = "down"
        self.frame_index = 0.0
        self.is_attacking = False

        self.image = self.animations[self.state][self.facing][0]
        self.rect  = self.image.get_rect(center=(x, y))

        # ── характеристики и прокачка ─────────────────────────────────────────
        self.stats     = Stats()
        self.inventory = Inventory()

        self.level = 1
        self.xp    = 0

        # текущее HP
        self._current_hp: float = float(self.stats.max_hp())

    # ── свойство hp ───────────────────────────────────────────────────────────
    @property
    def current_hp(self):
        return self._current_hp

    @current_hp.setter
    def current_hp(self, value):
        self._current_hp = max(0.0, min(float(value), float(self.stats.max_hp())))

    # ── загрузка анимаций ─────────────────────────────────────────────────────
    def load_animations(self, sheet, curr_y, frame_w, frame_h, frame_count, scale=1):
        frames = []
        for i in range(frame_count):
            frame = sheet.subsurface((i * frame_w, curr_y, frame_w, frame_h))
            if scale != 1:
                frame = pygame.transform.scale(
                    frame, (int(frame_w * scale), int(frame_h * scale)))
            frames.append(frame)
        return frames

    # ── опыт и уровни ─────────────────────────────────────────────────────────
    def gain_xp(self, amount: int):
        self.xp += amount
        needed = XP_PER_LEVEL * self.level
        while self.xp >= needed:
            self.xp   -= needed
            self.level += 1
            self.stats.free_points += STAT_POINTS_PER_LEVEL
            # восстановить HP при левел-апе
            self._current_hp = float(self.stats.max_hp())
            needed = XP_PER_LEVEL * self.level

    def xp_to_next(self):
        return XP_PER_LEVEL * self.level

    # ── получение урона ───────────────────────────────────────────────────────
    def take_damage(self, amount: float):
        self.current_hp -= amount

    # ── сериализация ──────────────────────────────────────────────────────────
    def to_dict(self):
        return {
            "x": self.rect.centerx,
            "y": self.rect.centery,
            "level": self.level,
            "xp": self.xp,
            "current_hp": self._current_hp,
            "stats": self.stats.to_dict(),
            "inventory": self.inventory.to_dict(),
        }

    def from_dict(self, d):
        cx = d.get("x", self.rect.centerx)
        cy = d.get("y", self.rect.centery)
        self.rect.center = (cx, cy)
        self.level = d.get("level", 1)
        self.xp    = d.get("xp",    0)
        self.stats.from_dict(d.get("stats", {}))
        self.inventory.from_dict(d.get("inventory", {}))
        self._current_hp = d.get("current_hp", float(self.stats.max_hp()))

    # ── обновление (вызывается каждый кадр) ──────────────────────────────────
    def update_player(self, keys, dt: float = 1.0):
        """dt — масштаб времени (1.0 = нормально, производное от clock.tick)."""
        if self.is_attacking:
            self.animate(dt)
            return

        moving = False
        self.state = "walk"
        mouse_click = pygame.mouse.get_pressed()
        spd = self.stats.speed() * dt

        if mouse_click[0]:
            self.state = "attack"
            self.is_attacking = True
            self.frame_index = 0.0
            moving = True
        else:
            if keys[pygame.K_w]:
                self.rect.y -= spd
                self.facing = "up"
                moving = True
            elif keys[pygame.K_s]:
                self.rect.y += spd
                self.facing = "down"
                moving = True

            if keys[pygame.K_a]:
                self.rect.x -= spd
                self.facing = "left"
                moving = True
            elif keys[pygame.K_d]:
                self.rect.x += spd
                self.facing = "right"
                moving = True

        if not moving:
            self.state = "idle"

        self.animate(dt)

    def animate(self, dt: float = 1.0):
        curr_anim = self.animations[self.state]
        curr_frames = curr_anim[self.facing]

        self.frame_index += curr_anim["speed"] * dt

        if self.frame_index >= len(curr_frames):
            self.frame_index = 0.0
            if self.is_attacking:
                self.is_attacking = False
                self.state = "idle"

        old_center = self.rect.center
        self.image = curr_frames[int(self.frame_index)]
        self.rect  = self.image.get_rect(center=old_center)

    def draw(self, screen, camera_x=0, camera_y=0):
        screen.blit(self.image, (self.rect.x - camera_x, self.rect.y - camera_y))