"""
core/pause_menu.py — экран паузы.

Переиспользует Button и цветовую палитру из core/menu.py.
Опции: "Продолжить", "Настройки", "Главное меню", "Выход".

Использование в main.py:
    pause = PauseMenu(screen, fonts)
    result = pause.handle_event(event)   # "resume" | "menu" | "quit" | None
    pause.draw(last_frame_surface)
"""

import pygame

# ─── Цветовая палитра (та же что в menu.py) ───────────────────────────────────
DARK_BG = (15, 17, 26)
PANEL_BG = (24, 28, 44)
ACCENT = (180, 140, 70)
ACCENT_HOVER = (220, 180, 90)
TEXT_MAIN = (220, 210, 190)
TEXT_DIM = (110, 100, 85)
BORDER = (60, 55, 40)
RED_EXIT = (160, 50, 50)
RED_EXIT_HOV = (200, 70, 70)

# Полупрозрачный оверлей поверх игры
OVERLAY_COLOR = (0, 0, 0, 160)


class _Button:
    """Локальная копия Button из menu.py — чтобы не создавать круговой импорт."""

    def __init__(self, rect, label, color_normal, color_hover, font,
                 text_color=TEXT_MAIN):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.color_normal = color_normal
        self.color_hover = color_hover
        self.font = font
        self.text_color = text_color
        self.hovered = False

    def draw(self, surface):
        color = self.color_hover if self.hovered else self.color_normal
        shadow = self.rect.move(3, 3)
        pygame.draw.rect(surface, (5, 5, 10), shadow, border_radius=6)
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        border_col = ACCENT if self.hovered else BORDER
        pygame.draw.rect(surface, border_col, self.rect, width=1, border_radius=6)
        txt = self.font.render(self.label, True, self.text_color)
        surface.blit(txt, txt.get_rect(center=self.rect.center))

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def is_clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos))


class PauseMenu:
    """
    Экран паузы. Рисуется поверх последнего кадра игры.

    Возвращаемые значения handle_event:
      "resume"  — продолжить игру
      "menu"    — вернуться в главное меню
      "quit"    — выход из приложения
      None      — событие не обработано
    """

    PANEL_W = 340
    PANEL_H = 320

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        W, H = screen.get_size()
        cx = W // 2

        font_title = pygame.font.SysFont(None, 46)
        font_body = pygame.font.SysFont(None, 30)

        self._font_title = font_title
        self._font_body = font_body

        # Центр панели
        bw, bh, gap = 260, 50, 12
        start_y = H // 2 - 60

        defs = [
            ("Продолжить", PANEL_BG, ACCENT, "resume"),
            ("Настройки", PANEL_BG, ACCENT, "settings"),
            ("Главное меню", PANEL_BG, ACCENT, "menu"),
            ("Выход", PANEL_BG, RED_EXIT, "quit"),
        ]
        self._buttons: list[tuple[_Button, str]] = []
        for i, (label, cn, ch, action) in enumerate(defs):
            y = start_y + i * (bh + gap)
            tc = TEXT_MAIN if action != "quit" else (220, 160, 160)
            btn = _Button((cx - bw // 2, y, bw, bh), label, cn, ch,
                          font_body, text_color=tc)
            self._buttons.append((btn, action))

        # Полупрозрачный оверлей
        self._overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        self._overlay.fill(OVERLAY_COLOR)

        # Фон панели
        self._panel_rect = pygame.Rect(
            cx - self.PANEL_W // 2,
            H // 2 - self.PANEL_H // 2,
            self.PANEL_W,
            self.PANEL_H,
        )

        # Состояние вложенных настроек (заглушка — открывает SettingsScreen)
        self._show_settings = False

    def handle_event(self, event, player=None) -> str | None:
        """
        Обрабатывает одно pygame-событие.
        Возвращает строку-команду или None.
        """
        for btn, action in self._buttons:
            if btn.is_clicked(event):
                return action
        return None

    def update(self, mouse_pos: tuple):
        for btn, _ in self._buttons:
            btn.update(mouse_pos)

    def draw(self, last_frame: pygame.Surface | None = None):
        """
        Рисует оверлей паузы поверх last_frame (или прямо на self.screen).
        """
        W, H = self.screen.get_size()

        if last_frame is not None:
            self.screen.blit(last_frame, (0, 0))

        # Затемняющий оверлей
        self.screen.blit(self._overlay, (0, 0))

        # Панель
        pygame.draw.rect(self.screen, PANEL_BG, self._panel_rect, border_radius=12)
        pygame.draw.rect(self.screen, BORDER, self._panel_rect, width=1, border_radius=12)

        # Заголовок «ПАУЗА»
        title = self._font_title.render("⏸  ПАУЗА", True, ACCENT)
        self.screen.blit(title, title.get_rect(
            centerx=W // 2,
            y=self._panel_rect.top + 18,
        ))

        # Разделитель
        lx = self._panel_rect.left + 20
        rx = self._panel_rect.right - 20
        pygame.draw.line(self.screen, BORDER,
                         (lx, self._panel_rect.top + 68),
                         (rx, self._panel_rect.top + 68), 1)

        # Кнопки
        for btn, _ in self._buttons:
            btn.draw(self.screen)
