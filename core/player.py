import pygame


class Player():

    def __init__(self, x, y):
        """инициализация игрока"""

        self.sprite_sheet = pygame.image.load('images/character-spritesheet.png').convert_alpha()

        self.frame_width = 64
        self.frame_height = 64

        self.animations = {
            "walk": {
                "down": self.load_animations(self.sprite_sheet, 640, 64, 64, 9),
                "left": self.load_animations(self.sprite_sheet, 576, 64, 64, 9),
                "right": self.load_animations(self.sprite_sheet, 704, 64, 64, 9),
                "up": self.load_animations(self.sprite_sheet, 512, 64, 64, 9),
                "speed": 0.2
            },
            "attack": {
                "down": self.load_animations(self.sprite_sheet, 3840, 192, 192, 6),
                "up": self.load_animations(self.sprite_sheet, 3456, 192, 192, 6),
                "left": self.load_animations(self.sprite_sheet, 3648, 192, 192, 6),
                "right": self.load_animations(self.sprite_sheet, 4032, 192, 192, 6),
                "speed": 0.25
            },
            "idle": {
                "down": self.load_animations(self.sprite_sheet, 1536, 64, 64, 2),
                "left": self.load_animations(self.sprite_sheet, 1472, 64, 64, 2),
                "up": self.load_animations(self.sprite_sheet, 1408, 64, 64, 2),
                "right": self.load_animations(self.sprite_sheet, 1600, 64, 64, 2),
                "speed": 0.05,
            }
        }

        self.state = "idle"
        self.facing = "down"
        self.frame_index = 0

        self.is_attacking = False

        self.image = self.animations[self.state][self.facing][self.frame_index]
        self.rect = self.image.get_rect(center=(x, y))

        self.speed = 4



    def load_animations(self, sheet, curr_y, frame_w, frame_h, frame_count):
        frames = []
        for i in range(frame_count):
            frame = sheet.subsurface((i * frame_w, curr_y, frame_w, frame_h))
            frames.append(frame)

        return frames

    def draw(self, screen):
        """отрисовка игрока"""
        screen.blit(self.image, self.rect)

    def update_player(self, keys):
        """обновление позиции игрока"""
        if self.is_attacking:
            self.animate()
            return


        moving = False
        self.state = 'walk'
        mouse_click = pygame.mouse.get_pressed()

        if mouse_click[0]:
            self.state = 'attack'
            self.is_attacking = True
            self.frame_index = 0
            moving = True
        else:
            if keys[pygame.K_w]:
                self.rect.y -= self.speed
                self.facing = "up"
                moving = True
            elif keys[pygame.K_s]:
                self.rect.y += self.speed
                self.facing = "down"
                moving = True

            if keys[pygame.K_a]:
                self.rect.x -= self.speed
                self.facing = "left"
                moving = True
            elif keys[pygame.K_d]:
                self.rect.x += self.speed
                self.facing = "right"
                moving = True

            # анимация только если движется
        if not moving:
            self.state = 'idle'

        self.animate()

    def animate(self):
        """Проигрывание анимации с центрированием"""
        curr_anim_data = self.animations[self.state]
        curr_frames = curr_anim_data[self.facing]

        self.frame_index += curr_anim_data["speed"]

        # Если анимация закончилась
        if self.frame_index >= len(curr_frames):
            self.frame_index = 0
            # Если это была атака — выключаем её
            if self.is_attacking:
                self.is_attacking = False
                self.state = 'idle'

        # Центрирование: запоминаем старый центр и ставим туда новую картинку
        old_center = self.rect.center
        self.image = curr_frames[int(self.frame_index)]
        self.rect = self.image.get_rect(center=old_center)
