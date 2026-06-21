import pygame
import json
import os
import sys

from core.save_system import list_saves, delete_save

# ─── Цветовая палитра ──────────────────────────────────────────────────────────
DARK_BG = (15, 17, 26)  # почти чёрный, чуть синеватый
PANEL_BG = (24, 28, 44)  # тёмно-синяя панель
ACCENT = (180, 140, 70)  # старое золото — как рунные надписи
ACCENT_HOVER = (220, 180, 90)  # яркое золото при наведении
TEXT_MAIN = (220, 210, 190)  # пергаментный белый
TEXT_DIM = (110, 100, 85)  # приглушённый текст
BORDER = (60, 55, 40)  # тёмная рамка
SEPARATOR = (40, 38, 30)  # разделитель
RED_EXIT = (160, 50, 50)
RED_EXIT_HOV = (200, 70, 70)


# ─── Вспомогательный класс кнопки ─────────────────────────────────────────────
class Button:
    def __init__(self, rect, label, color_normal, color_hover, font, text_color=TEXT_MAIN):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.color_normal = color_normal
        self.color_hover = color_hover
        self.font = font
        self.text_color = text_color
        self.hovered = False

    def draw(self, surface):
        color = self.color_hover if self.hovered else self.color_normal

        # тень
        shadow = self.rect.move(3, 3)
        pygame.draw.rect(surface, (5, 5, 10), shadow, border_radius=6)

        # тело кнопки
        pygame.draw.rect(surface, color, self.rect, border_radius=6)

        # рамка
        border_col = ACCENT if self.hovered else BORDER
        pygame.draw.rect(surface, border_col, self.rect, width=1, border_radius=6)

        # текст
        txt = self.font.render(self.label, True, self.text_color)
        surface.blit(txt, txt.get_rect(center=self.rect.center))

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def is_clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos))


# ─── Слайдер ──────────────────────────────────────────────────────────────────
class Slider:
    def __init__(self, x, y, width, label, value=0.5, font=None):
        self.x = x
        self.y = y
        self.width = width
        self.label = label
        self.value = value  # 0.0 – 1.0
        self.font = font
        self.track_h = 4
        self.knob_r = 8
        self.dragging = False

    @property
    def track_rect(self):
        return pygame.Rect(self.x, self.y + self.knob_r - self.track_h // 2,
                           self.width, self.track_h)

    @property
    def knob_center(self):
        return (int(self.x + self.value * self.width), self.y + self.knob_r)

    def draw(self, surface):
        # подпись
        lbl = self.font.render(self.label, True, TEXT_MAIN)
        surface.blit(lbl, (self.x, self.y - 22))

        # процент
        pct = self.font.render(f"{int(self.value * 100)}%", True, ACCENT)
        surface.blit(pct, (self.x + self.width + 12, self.y - 2))

        # трек (заполненная часть)
        filled = pygame.Rect(self.x, self.track_rect.y,
                             int(self.value * self.width), self.track_h)
        pygame.draw.rect(surface, SEPARATOR, self.track_rect, border_radius=2)
        pygame.draw.rect(surface, ACCENT, filled, border_radius=2)

        # ручка
        kx, ky = self.knob_center
        pygame.draw.circle(surface, PANEL_BG, (kx, ky), self.knob_r)
        pygame.draw.circle(surface, ACCENT, (kx, ky), self.knob_r, 2)

    def handle_event(self, event):
        kx, ky = self.knob_center
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            dx, dy = event.pos[0] - kx, event.pos[1] - ky
            if dx * dx + dy * dy <= (self.knob_r + 4) ** 2:
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            raw = (event.pos[0] - self.x) / self.width
            self.value = max(0.0, min(1.0, raw))


# ─── Экран настроек ───────────────────────────────────────────────────────────
class SettingsScreen:
    RESOLUTIONS = [(1280, 720), (1600, 900), (1920, 1080), (2560, 1440)]

    def __init__(self, screen, fonts, settings):
        self.screen = screen
        self.fonts = fonts
        self.settings = settings  # словарь: music, sfx, resolution_idx

        W, H = screen.get_size()
        cx = W // 2

        # слайдеры
        slider_w = 300
        sx = cx - slider_w // 2
        self.slider_music = Slider(sx, H // 2 - 120, slider_w, "Музыка",
                                   value=settings.get("music", 0.7), font=fonts["body"])
        self.slider_sfx = Slider(sx, H // 2 - 40, slider_w, "Звуковые эффекты",
                                 value=settings.get("sfx", 0.8), font=fonts["body"])

        # кнопки разрешения
        self.res_idx = settings.get("resolution_idx", 2)

        bw, bh = 140, 36
        self._make_res_buttons(cx, H // 2 + 60, bw, bh)

        # назад
        self.btn_back = Button((cx - 80, H - 80, 160, 44),
                               "← Назад", PANEL_BG, BORDER, fonts["body"])

    def _make_res_buttons(self, cx, y, bw, bh):
        n = len(self.RESOLUTIONS)
        gap = 10
        total = n * bw + (n - 1) * gap
        start = cx - total // 2
        self.res_buttons = []
        for i, (rw, rh) in enumerate(self.RESOLUTIONS):
            x = start + i * (bw + gap)
            self.res_buttons.append(
                Button((x, y, bw, bh), f"{rw}×{rh}",
                       PANEL_BG, ACCENT, self.fonts["small"])
            )

    def handle_event(self, event):
        self.slider_music.handle_event(event)
        self.slider_sfx.handle_event(event)

        if self.btn_back.is_clicked(event):
            # сохраняем значения обратно
            self.settings["music"] = self.slider_music.value
            self.settings["sfx"] = self.slider_sfx.value
            self.settings["resolution_idx"] = self.res_idx
            return "back"

        for i, btn in enumerate(self.res_buttons):
            if btn.is_clicked(event):
                self.res_idx = i

        return None

    def update(self, mouse_pos):
        self.btn_back.update(mouse_pos)
        for btn in self.res_buttons:
            btn.update(mouse_pos)

    def draw(self):
        W, H = self.screen.get_size()
        self.screen.fill(DARK_BG)

        # заголовок
        title = self.fonts["title"].render("Настройки", True, ACCENT)
        self.screen.blit(title, title.get_rect(centerx=W // 2, y=60))
        pygame.draw.line(self.screen, BORDER, (W // 2 - 200, 115), (W // 2 + 200, 115), 1)

        # слайдеры
        self.slider_music.draw(self.screen)
        self.slider_sfx.draw(self.screen)

        # секция разрешения
        lbl_res = self.fonts["body"].render("Разрешение", True, TEXT_MAIN)
        self.screen.blit(lbl_res, lbl_res.get_rect(centerx=W // 2, y=self.res_buttons[0].rect.y - 28))
        for i, btn in enumerate(self.res_buttons):
            # подсветить выбранное
            if i == self.res_idx:
                pygame.draw.rect(self.screen, ACCENT, btn.rect, border_radius=6)
                txt = self.fonts["small"].render(btn.label, True, DARK_BG)
                self.screen.blit(txt, txt.get_rect(center=btn.rect.center))
            else:
                btn.draw(self.screen)

        self.btn_back.draw(self.screen)


# ─── Экран загрузки сохранений ────────────────────────────────────────────────
class LoadScreen:
    """
    Показывает список реальных сохранений (через core.save_system.list_saves).
    Поддерживает выбор слота, загрузку и удаление выбранного сохранения.
    """

    def __init__(self, screen, fonts):
        self.screen = screen
        self.fonts = fonts
        self.saves = list_saves()
        self.selected = None

        W, H = screen.get_size()
        cx = W // 2

        self.slot_rects = []
        slot_w, slot_h, gap = 500, 60, 12
        count = max(1, len(self.saves))
        start_y = H // 2 - (count * (slot_h + gap)) // 2
        for i in range(len(self.saves)):
            rx = cx - slot_w // 2
            ry = start_y + i * (slot_h + gap)
            self.slot_rects.append(pygame.Rect(rx, ry, slot_w, slot_h))

        # кнопки
        self.btn_load = Button((cx - 260, H - 90, 150, 44),
                               "Загрузить", PANEL_BG, ACCENT, fonts["body"])
        self.btn_delete = Button((cx - 90, H - 90, 150, 44),
                                 "Удалить", PANEL_BG, RED_EXIT_HOV, fonts["body"],
                                 text_color=(230, 190, 190))
        self.btn_back = Button((cx + 90, H - 90, 150, 44),
                               "← Назад", PANEL_BG, BORDER, fonts["body"])

    def _refresh(self):
        """Перестраивает список после удаления сохранения."""
        self.saves = list_saves()
        self.selected = None

        W, H = self.screen.get_size()
        cx = W // 2
        self.slot_rects = []
        slot_w, slot_h, gap = 500, 60, 12
        count = max(1, len(self.saves))
        start_y = H // 2 - (count * (slot_h + gap)) // 2
        for i in range(len(self.saves)):
            rx = cx - slot_w // 2
            ry = start_y + i * (slot_h + gap)
            self.slot_rects.append(pygame.Rect(rx, ry, slot_w, slot_h))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self.slot_rects):
                if r.collidepoint(event.pos):
                    self.selected = i

        if self.btn_back.is_clicked(event):
            return "back"

        if self.btn_load.is_clicked(event):
            if self.selected is not None and self.saves:
                return ("load", self.saves[self.selected]["file"])

        if self.btn_delete.is_clicked(event):
            if self.selected is not None and self.saves:
                delete_save(self.saves[self.selected]["file"])
                self._refresh()

        return None

    def update(self, mouse_pos):
        self.btn_back.update(mouse_pos)
        self.btn_load.update(mouse_pos)
        self.btn_delete.update(mouse_pos)

    def draw(self):
        W, H = self.screen.get_size()
        self.screen.fill(DARK_BG)

        title = self.fonts["title"].render("Загрузить игру", True, ACCENT)
        self.screen.blit(title, title.get_rect(centerx=W // 2, y=60))
        pygame.draw.line(self.screen, BORDER, (W // 2 - 220, 115), (W // 2 + 220, 115), 1)

        if not self.saves:
            msg = self.fonts["body"].render("Сохранения не найдены", True, TEXT_DIM)
            self.screen.blit(msg, msg.get_rect(center=(W // 2, H // 2)))
        else:
            for i, (r, sv) in enumerate(zip(self.slot_rects, self.saves)):
                selected = (i == self.selected)
                bg = ACCENT if selected else PANEL_BG
                pygame.draw.rect(self.screen, bg, r, border_radius=6)
                bc = ACCENT_HOVER if selected else BORDER
                pygame.draw.rect(self.screen, bc, r, width=1, border_radius=6)

                tc = DARK_BG if selected else TEXT_MAIN
                name_s = self.fonts["body"].render(sv["name"], True, tc)
                info_s = self.fonts["small"].render(
                    f"Уровень: {sv['level']}   |   Время: {sv['time']}",
                    True, DARK_BG if selected else TEXT_DIM)
                self.screen.blit(name_s, (r.x + 16, r.y + 8))
                self.screen.blit(info_s, (r.x + 16, r.y + 34))

        self.btn_load.draw(self.screen)
        self.btn_delete.draw(self.screen)
        self.btn_back.draw(self.screen)


# ─── Главное меню ─────────────────────────────────────────────────────────────
class MainMenu:
    """
    Использование:
        menu = MainMenu(screen)
        result = menu.run()   # возвращает "new_game" | "load:<path>" | "quit"
    """

    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.settings = {"music": 0.7, "sfx": 0.8, "resolution_idx": 2}
        self._load_settings()

        self.fonts = self._build_fonts()
        self._build_buttons()

        self.state = "main"  # "main" | "settings" | "load"
        self.sub_screen = None

        # частицы-звёзды
        import random
        W, H = screen.get_size()
        self.stars = [
            {"x": random.randint(0, W), "y": random.randint(0, H),
             "r": random.uniform(0.5, 2.0), "alpha": random.randint(40, 180)}
            for _ in range(120)
        ]

    # ── шрифты ────────────────────────────────────────────────────────────────
    def _build_fonts(self):
        # предпочитаем системные шрифты с засечками (если есть)
        serif_candidates = ["garamond", "palatino", "times new roman",
                            "georgia", "serif", "freesans", "dejavuserif",
                            "notoserifcjksc", None]
        display_font = None
        for name in serif_candidates:
            f = pygame.font.SysFont(name, 52, bold=True)
            if f:
                display_font = f
                break

        return {
            "title": display_font,
            "sub": pygame.font.SysFont(None, 26),
            "body": pygame.font.SysFont(None, 28),
            "small": pygame.font.SysFont(None, 22),
        }

    # ── кнопки главного меню ──────────────────────────────────────────────────
    def _build_buttons(self):
        W, H = self.screen.get_size()
        cx = W // 2
        bw, bh, gap = 260, 52, 14
        # вертикальный стек с небольшим смещением вниз от центра
        start_y = H // 2 - 20

        defs = [
            ("Новая игра", PANEL_BG, ACCENT, "new_game"),
            ("Загрузить игру", PANEL_BG, ACCENT, "load"),
            ("Настройки", PANEL_BG, ACCENT, "settings"),
            ("Выход", PANEL_BG, RED_EXIT, "quit"),
        ]
        self.buttons = []
        for i, (label, cn, ch, action) in enumerate(defs):
            y = start_y + i * (bh + gap)
            tc = TEXT_MAIN if action != "quit" else (220, 160, 160)
            btn = Button((cx - bw // 2, y, bw, bh), label, cn, ch,
                         self.fonts["body"], text_color=tc)
            btn.action = action
            self.buttons.append(btn)

    # ── настройки на диске ────────────────────────────────────────────────────
    def _load_settings(self):
        path = "saves/settings.json"
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    self.settings.update(json.load(f))
            except Exception:
                pass

    def _save_settings(self):
        os.makedirs("saves", exist_ok=True)
        with open("saves/settings.json", "w") as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)

    # ── декоративный фон ──────────────────────────────────────────────────────
    def _draw_background(self):
        W, H = self.screen.get_size()
        self.screen.fill(DARK_BG)

        # звёзды
        star_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        for s in self.stars:
            pygame.draw.circle(star_surf, (*TEXT_DIM, s["alpha"]),
                               (int(s["x"]), int(s["y"])), s["r"])
        self.screen.blit(star_surf, (0, 0))

        # тонкая вертикальная полоска-акцент слева
        pygame.draw.rect(self.screen, ACCENT, (0, 0, 3, H))

    def _draw_title(self):
        W, H = self.screen.get_size()
        title = self.fonts["title"].render("Cursed Land", True, ACCENT)
        sub = self.fonts["sub"].render("v0.1  —  Demo Build", True, TEXT_DIM)

        ty = H // 2 - 190
        self.screen.blit(title, title.get_rect(centerx=W // 2, y=ty))

        # линия под заголовком
        lw = 280
        pygame.draw.line(self.screen, BORDER,
                         (W // 2 - lw // 2, ty + title.get_height() + 6),
                         (W // 2 + lw // 2, ty + title.get_height() + 6), 1)
        self.screen.blit(sub, sub.get_rect(centerx=W // 2,
                                           y=ty + title.get_height() + 14))

    # ── основной цикл ─────────────────────────────────────────────────────────
    def run(self):
        while True:
            self.clock.tick(60)
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"

                if self.state == "main":
                    for btn in self.buttons:
                        if btn.is_clicked(event):
                            if btn.action == "quit":
                                self._save_settings()
                                return "quit"
                            elif btn.action == "new_game":
                                return "new_game"
                            elif btn.action == "settings":
                                self.state = "settings"
                                self.sub_screen = SettingsScreen(
                                    self.screen, self.fonts, self.settings)
                            elif btn.action == "load":
                                self.state = "load"
                                self.sub_screen = LoadScreen(
                                    self.screen, self.fonts)

                elif self.state == "settings":
                    result = self.sub_screen.handle_event(event)
                    if result == "back":
                        self._save_settings()
                        self.state = "main"
                        self.sub_screen = None

                elif self.state == "load":
                    result = self.sub_screen.handle_event(event)
                    if result == "back":
                        self.state = "main"
                        self.sub_screen = None
                    elif isinstance(result, tuple) and result[0] == "load":
                        return f"load:{result[1]}"

            # обновление hover
            if self.state == "main":
                for btn in self.buttons:
                    btn.update(mouse_pos)
            elif self.sub_screen:
                self.sub_screen.update(mouse_pos)

            # отрисовка
            if self.state == "main":
                self._draw_background()
                self._draw_title()
                for btn in self.buttons:
                    btn.draw(self.screen)
            elif self.sub_screen:
                self.sub_screen.draw()

            pygame.display.flip()