"""
core/death_screen.py — экран гибели персонажа (Game Over).

Переиспользует цветовую палитру из core/menu.py / core/pause_menu.py
(намеренное небольшое дублирование маленького стабильного набора
констант — та же причина, что и в core/pause_menu.py: избежать кругового
импорта между модулями экранов).

Показывается, когда player.is_dead == True и анимация/пауза смерти
завершена (player.death_animation_finished). Рисуется поверх затемнённого
последнего кадра игры — по тому же принципу, что и PauseMenu.

Опции: "Начать заново" (новая игра с текущим уровнем сложности волн с нуля),
"Главное меню", "Выход".

Использование в main.py:
    death_screen = DeathScreen(screen)
    ...
    result = death_screen.handle_event(event)  # "restart" | "menu" | "quit" | None
    death_screen.draw(last_frame_surface, player)
"""

import pygame

# ─── Цветовая палитра (та же что в menu.py / pause_menu.py) ───────────────────
DARK_BG = (15, 17, 26)
PANEL_BG = (24, 28, 44)
ACCENT = (180, 140, 70)
ACCENT_HOVER = (220, 180, 90)
TEXT_MAIN = (220, 210, 190)
TEXT_DIM = (110, 100, 85)
BORDER = (60, 55, 40)
RED_EXIT = (160, 50, 50)
RED_EXIT_HOV = (200, 70, 70)
RED_TITLE = (180, 40, 40)

# Затемнение сильнее, чем у паузы — гибель должна ощущаться весомее
OVERLAY_COLOR = (10, 0, 0, 195)

# Скорость нарастания затемнения и заголовка после смерти, мс
FADE_IN_MS = 900


class _Button:
    """Локальная копия Button — см. core/pause_menu.py о причине дублирования."""

    def __init__(self, rect, label, color_normal, color_hover, font,
                 text_color=TEXT_MAIN):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.color_normal = color_normal
        self.color_hover = color_hover
        self.font = font
        self.text_color = text_color
        self.hovered = False

    def draw(self, surface, alpha: int = 255):
        color = self.color_hover if self.hovered else self.color_normal
        btn_surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(btn_surf, (*color, alpha), btn_surf.get_rect(), border_radius=6)
        border_col = ACCENT if self.hovered else BORDER
        pygame.draw.rect(btn_surf, (*border_col, alpha), btn_surf.get_rect(),
                         width=1, border_radius=6)
        txt = self.font.render(self.label, True, self.text_color)
        txt.set_alpha(alpha)
        btn_surf.blit(txt, txt.get_rect(center=(self.rect.width // 2, self.rect.height // 2)))
        surface.blit(btn_surf, self.rect.topleft)

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def is_clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos))


class DeathScreen:
    """
    Экран гибели персонажа. Рисуется поверх последнего кадра игры
    (тёмно-красный оверлей вместо нейтрального оверлея паузы).

    Возвращаемые значения handle_event:
      "restart" — начать новую игру (тот же save_path=None сценарий, что и
                  «Новая игра» из главного меню — игрок стартует заново)
      "menu"    — вернуться в главное меню
      "quit"    — выход из приложения
      None      — событие не обработано (или экран ещё не активен)
    """

    PANEL_W = 320
    PANEL_H = 260

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        W, H = screen.get_size()
        cx = W // 2

        self._font_title = pygame.font.SysFont(None, 64, bold=True)
        self._font_stats = pygame.font.SysFont(None, 28)
        font_body = pygame.font.SysFont(None, 30)

        bw, bh, gap = 280, 50, 14
        start_y = H // 2 - 130

        defs = [
            ("Начать заново", PANEL_BG, ACCENT, "restart"),
            ("Главное меню", PANEL_BG, ACCENT, "menu"),
            ("Выход", PANEL_BG, RED_EXIT, "quit"),
        ]
        self._buttons: list[tuple[_Button, str]] = []
        for i, (label, cn, ch, action) in enumerate(defs):
            y = start_y + i * (bh + gap)
            tc = TEXT_MAIN if action != "quit" else (230, 180, 180)
            btn = _Button((cx - bw // 2, y, bw, bh), label, cn, ch,
                          font_body, text_color=tc)
            self._buttons.append((btn, action))

        self._overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        self._overlay.fill(OVERLAY_COLOR)

        self._panel_rect = pygame.Rect(
            cx - self.PANEL_W // 2,
            H // 2 - self.PANEL_H // 2 - 30,
            self.PANEL_W,
            self.PANEL_H,
        )

        # Таймер для плавного нарастания затемнения/заголовка при первом показе
        self._shown_since_ms: int | None = None

    def reset_fade(self):
        """Вызывать один раз, когда экран впервые становится активным —
        запускает fade-in эффект заново (полезно при повторной смерти после revive)."""
        self._shown_since_ms = pygame.time.get_ticks()

    def _current_alpha(self) -> int:
        if self._shown_since_ms is None:
            return 255
        elapsed = pygame.time.get_ticks() - self._shown_since_ms
        return max(0, min(255, int(255 * elapsed / FADE_IN_MS)))

    def handle_event(self, event) -> str | None:
        for btn, action in self._buttons:
            if btn.is_clicked(event):
                return action
        return None

    def update(self, mouse_pos: tuple):
        for btn, _ in self._buttons:
            btn.update(mouse_pos)

    def draw(self, last_frame: pygame.Surface | None, player=None):
        """
        Рисует оверлей гибели поверх last_frame.

        player — опционально, если передан, под заголовком показывается
        краткая статистика (достигнутый уровень) — чисто информативно,
        ничего не меняет в состоянии player.
        """
        W, H = self.screen.get_size()
        alpha = self._current_alpha()

        if last_frame is not None:
            self.screen.blit(last_frame, (0, 0))

        overlay_faded = self._overlay.copy()
        # Применяем нарастающую альфу к копии оверлея, не трогая оригинал
        overlay_faded.fill((0, 0, 0, 0))
        overlay_faded.blit(self._overlay, (0, 0))
        if alpha < 255:
            fade_mask = pygame.Surface((W, H), pygame.SRCALPHA)
            fade_mask.fill((0, 0, 0, 255 - alpha))
            overlay_faded.blit(fade_mask, (0, 0),
                               special_flags=pygame.BLEND_RGBA_SUB)
        self.screen.blit(overlay_faded, (0, 0))

        # Заголовок «ВЫ ПОГИБЛИ»
        title = self._font_title.render("ВЫ ПОГИБЛИ", True, RED_TITLE)
        title.set_alpha(alpha)
        self.screen.blit(title, title.get_rect(
            centerx=W // 2, y=self._panel_rect.top - 70))

        if player is not None:
            stats_txt = self._font_stats.render(
                f"Уровень: {player.level}", True, TEXT_DIM)
            stats_txt.set_alpha(alpha)
            self.screen.blit(stats_txt, stats_txt.get_rect(
                centerx=W // 2, y=self._panel_rect.top - 16))

        # Панель с кнопками
        panel_surf = pygame.Surface(self._panel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (*PANEL_BG, min(alpha, 230)),
                         panel_surf.get_rect(), border_radius=12)
        pygame.draw.rect(panel_surf, (*BORDER, alpha),
                         panel_surf.get_rect(), width=1, border_radius=12)
        self.screen.blit(panel_surf, self._panel_rect.topleft)

        for btn, _ in self._buttons:
            btn.draw(self.screen, alpha=alpha)