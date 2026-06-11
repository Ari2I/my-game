"""
HUD — нижняя панель в стиле Dota 2.

Структура панели (снизу по центру экрана):
 ┌──────────────────────────────────────────────────────────────────────┐
 │  [HP бар]      [Lvl N  XP bar]     [Сила][Ловк][Вит]  [Слизь: N]  │
 │  [Иконка]  HP: N/N   Урон: N  Скорость: N.N  [+кнопки если очки]  │
 └──────────────────────────────────────────────────────────────────────┘
"""

import pygame


# ── Цвета ─────────────────────────────────────────────────────────────────────
C_PANEL_BG  = (18,  20,  30,  220)   # фон панели (RGBA)
C_PANEL_BOR = (60,  55,  40,  255)
C_HP_FULL   = (60, 180,  80)
C_HP_LOW    = (200,  55,  50)
C_HP_BG     = (40,  20,  20)
C_XP_FILL   = (80, 140, 230)
C_XP_BG     = (20,  30,  50)
C_GOLD      = (200, 165,  60)
C_WHITE     = (220, 210, 190)
C_DIM       = (110, 100,  85)
C_GREEN_BTN = (40,  130,  60)
C_GREEN_HOV = (60,  170,  80)
C_SLIME     = (120, 200,  80)

PANEL_H    = 110   # высота панели
PANEL_W    = 780   # ширина панели
BAR_H      = 16    # высота полосок


class PlusButton:
    """Маленькая кнопка «+» для вложения очка характеристики."""

    SIZE = 20

    def __init__(self, x, y, stat_name, font):
        self.rect = pygame.Rect(x, y, self.SIZE, self.SIZE)
        self.stat = stat_name
        self.font = font
        self.hovered = False

    def draw(self, surface):
        color = C_GREEN_HOV if self.hovered else C_GREEN_BTN
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        pygame.draw.rect(surface, C_GOLD, self.rect, width=1, border_radius=4)
        lbl = self.font.render("+", True, C_WHITE)
        surface.blit(lbl, lbl.get_rect(center=self.rect.center))

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def is_clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos))


class HUD:
    """
    Использование:
        hud = HUD(screen_width, screen_height)
        ...
        hud.handle_event(event, player)
        hud.draw(screen, player)
    """

    def __init__(self, screen_w: int, screen_h: int):
        self.sw = screen_w
        self.sh = screen_h

        # координаты левого верхнего угла панели
        self.px = (screen_w - PANEL_W) // 2
        self.py = screen_h - PANEL_H - 8

        self._build_fonts()
        self._build_layout()

        # кэш surface панели (перерисовываем только при изменениях)
        self._panel_surf = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)

    # ── шрифты ────────────────────────────────────────────────────────────────
    def _build_fonts(self):
        self.f_label  = pygame.font.SysFont(None, 20)
        self.f_value  = pygame.font.SysFont(None, 24)
        self.f_big    = pygame.font.SysFont(None, 28)
        self.f_lvl    = pygame.font.SysFont(None, 22)

    # ── расположение элементов внутри панели ──────────────────────────────────
    def _build_layout(self):
        # кнопки «+» — пересчитываются в draw() при наличии свободных очков
        self._plus_buttons: list[PlusButton] = []

    # ── обработка событий ─────────────────────────────────────────────────────
    def handle_event(self, event, player):
        for btn in self._plus_buttons:
            if btn.is_clicked(event):
                old_max = player.stats.max_hp()
                if player.stats.add_point(btn.stat):
                    # если максимум HP вырос — масштабируем текущее HP
                    new_max = player.stats.max_hp()
                    if btn.stat == "vitality":
                        player.current_hp += (new_max - old_max)

    def update(self, mouse_pos):
        for btn in self._plus_buttons:
            btn.update(mouse_pos)

    # ── вспомогательный рисовальщик полоски ──────────────────────────────────
    @staticmethod
    def _draw_bar(surf, x, y, w, h, value, max_value, color_fill, color_bg):
        pygame.draw.rect(surf, color_bg, (x, y, w, h), border_radius=4)
        if max_value > 0:
            filled = max(0, int(w * value / max_value))
            if filled > 0:
                pygame.draw.rect(surf, color_fill, (x, y, filled, h), border_radius=4)
        pygame.draw.rect(surf, (50, 50, 50), (x, y, w, h), width=1, border_radius=4)

    # ── основная отрисовка ────────────────────────────────────────────────────
    def draw(self, screen, player):
        surf = self._panel_surf
        surf.fill((0, 0, 0, 0))

        # фон панели
        pygame.draw.rect(surf, C_PANEL_BG,  (0, 0, PANEL_W, PANEL_H), border_radius=10)
        pygame.draw.rect(surf, C_PANEL_BOR, (0, 0, PANEL_W, PANEL_H),
                         width=1, border_radius=10)

        stats  = player.stats
        inv    = player.inventory
        max_hp = stats.max_hp()
        hp     = player.current_hp
        lvl    = player.level
        xp     = player.xp
        xp_max = player.xp_to_next()

        # ── левая колонка: HP ─────────────────────────────────────────────────
        lx, ly = 16, 14

        # иконка ♥ + «HP»
        hp_lbl = self.f_label.render("❤  HP", True, C_WHITE)
        surf.blit(hp_lbl, (lx, ly))

        # полоска HP
        bar_w = 200
        hp_ratio = hp / max_hp if max_hp > 0 else 0
        hp_color = _lerp_color(C_HP_LOW, C_HP_FULL, hp_ratio)
        self._draw_bar(surf, lx, ly + 20, bar_w, BAR_H,
                       hp, max_hp, hp_color, C_HP_BG)

        # числа на полоске
        hp_txt = self.f_lvl.render(f"{int(hp)} / {max_hp}", True, C_WHITE)
        surf.blit(hp_txt, hp_txt.get_rect(
            centerx=lx + bar_w // 2, centery=ly + 20 + BAR_H // 2))

        # ── средне-левая: уровень + XP ───────────────────────────────────────
        mx = lx + bar_w + 20

        lvl_txt = self.f_big.render(f"Ур. {lvl}", True, C_GOLD)
        surf.blit(lvl_txt, (mx, ly - 2))

        xp_lbl = self.f_label.render("Опыт", True, C_DIM)
        surf.blit(xp_lbl, (mx, ly + 24))
        self._draw_bar(surf, mx, ly + 38, 130, 10,
                       xp, xp_max, C_XP_FILL, C_XP_BG)
        xp_num = self.f_lvl.render(f"{xp}/{xp_max}", True, C_DIM)
        surf.blit(xp_num, (mx, ly + 52))

        # ── центр: основные статы ─────────────────────────────────────────────
        cx2 = mx + 160
        pad_y = 10

        stat_lines = [
            ("⚔  Атака",  f"{stats.damage()}",     C_WHITE),
            ("👟  Скорость", f"{stats.speed():.1f}", C_WHITE),
            ("❤  Вит.",   f"{stats.vitality}",      C_WHITE),
            ("⚡  Сила",   f"{stats.power}",          C_WHITE),
            ("🌿  Ловк.",  f"{stats.agility}",        C_WHITE),
        ]

        for i, (label, val, col) in enumerate(stat_lines):
            lbl_s = self.f_label.render(label, True, C_DIM)
            val_s = self.f_value.render(val,   True, col)
            y_row = pad_y + i * 20
            surf.blit(lbl_s, (cx2, y_row))
            surf.blit(val_s, (cx2 + 110, y_row - 1))

        # ── кнопки «+» если есть свободные очки ──────────────────────────────
        self._plus_buttons.clear()
        if stats.free_points > 0:
            # точка-уведомление
            fp_txt = self.f_big.render(
                f"Очки: {stats.free_points}", True, C_GOLD)
            surf.blit(fp_txt, (cx2, PANEL_H - 28))

            btn_defs = [
                ("vitality",  cx2 + 88, pad_y + 2 * 20),
                ("power",     cx2 + 88, pad_y + 3 * 20),
                ("agility",   cx2 + 88, pad_y + 4 * 20),
            ]
            for stat_name, bx, by in btn_defs:
                abs_x = self.px + bx
                abs_y = self.py + by
                btn = PlusButton(abs_x, abs_y, stat_name, self.f_lvl)
                self._plus_buttons.append(btn)
                # рисуем прямо на панели (координаты локальные)
                tmp = PlusButton(bx, by, stat_name, self.f_lvl)
                tmp.hovered = any(b.stat == stat_name and b.hovered
                                  for b in self._plus_buttons)
                tmp.draw(surf)

        # ── правая колонка: ресурсы ───────────────────────────────────────────
        rx = PANEL_W - 160
        res_lbl = self.f_label.render("Ресурсы", True, C_DIM)
        surf.blit(res_lbl, (rx, 10))

        # слизь слаймов
        slime_icon = self.f_value.render("🟢", True, C_SLIME)
        slime_val  = self.f_value.render(str(inv.slime_goo), True, C_WHITE)
        slime_lbl  = self.f_label.render("Слизь слаймов", True, C_DIM)
        surf.blit(slime_icon, (rx,      32))
        surf.blit(slime_val,  (rx + 28, 34))
        surf.blit(slime_lbl,  (rx,      56))

        # ── блиттим панель на экран ───────────────────────────────────────────
        screen.blit(surf, (self.px, self.py))

        # кнопки «+» поверх (они рисуются прямо на surf, но hover нужен отдельно)
        # уже вставлены в surf выше


# ── вспомогательная: линейная интерполяция цвета ──────────────────────────────
def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))