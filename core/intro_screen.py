"""
core/intro_screen.py — экран сюжетной завязки.

Текст загружается из data/story.json — данные отделены от кода (принцип SRP).
Показывается перед стартом новой игры, пропускается по ПРОБЕЛ/ENTER/ESC.

Структура story.json:
    {
      "title": "Название",
      "slides": [
        {"heading": "Заголовок слайда", "text": "Текст..."},
        ...
      ],
      "prompt": "Подсказка пользователю"
    }

Использование в main.py:
    intro = IntroScreen(screen)
    result = intro.run()   # "done" | "skip"
"""

import json
import os
import pygame

# ─── Путь к файлу с текстом ───────────────────────────────────────────────────
STORY_FILE = os.path.join("data", "story.json")

# ─── Цвета ────────────────────────────────────────────────────────────────────
C_BG        = (10,  12,  20)
C_TITLE     = (180, 140,  70)
C_HEADING   = (220, 200, 140)
C_TEXT      = (190, 185, 170)
C_PROMPT    = (100,  95,  80)
C_STAR      = (150, 145, 130)

# ─── Параметры анимации ───────────────────────────────────────────────────────
SLIDE_FADE_MS  = 600    # мс на fade-in слайда
SLIDE_HOLD_MS  = 3500   # мс показа слайда
AUTO_ADVANCE   = True   # автоматический переход между слайдами


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Переносит длинный текст по словам, возвращает список строк."""
    words  = text.split()
    lines  = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class IntroScreen:
    """
    Экран с несколькими слайдами сюжетной завязки.

    Навигация:
      - ПРОБЕЛ / ENTER / ЛКМ — следующий слайд / пропуск
      - ESC — немедленный выход
    """

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock  = pygame.time.Clock()
        self._data  = self._load_story()

        W, H = screen.get_size()
        self._W = W
        self._H = H

        self._font_title   = pygame.font.SysFont(None, 52)
        self._font_heading = pygame.font.SysFont(None, 36)
        self._font_body    = pygame.font.SysFont(None, 27)
        self._font_prompt  = pygame.font.SysFont(None, 22)

        # Декоративные звёзды
        import random
        self._stars = [
            (random.randint(0, W), random.randint(0, H),
             random.uniform(0.5, 1.8), random.randint(30, 120))
            for _ in range(100)
        ]

    # ── загрузка данных ───────────────────────────────────────────────────────
    @staticmethod
    def _load_story() -> dict:
        """Загружает данные из story.json. При ошибке — возвращает заглушку."""
        try:
            with open(STORY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[IntroScreen] Не удалось загрузить {STORY_FILE}: {e}")
            return {
                "title": "Cursed Land",
                "slides": [{"heading": "", "text": "Добро пожаловать!"}],
                "prompt": "Нажми ПРОБЕЛ чтобы начать",
            }

    # ── основной цикл ─────────────────────────────────────────────────────────
    def run(self) -> str:
        """Запускает экран. Возвращает 'done' или 'skip'."""
        slides      = self._data.get("slides", [])
        title_text  = self._data.get("title",  "Cursed Land")
        prompt_text = self._data.get("prompt", "Нажми ПРОБЕЛ")

        if not slides:
            return "done"

        # Сначала показываем заголовок отдельным экраном
        result = self._show_title(title_text, prompt_text)
        if result == "skip":
            return "skip"

        # Показываем слайды
        for i, slide in enumerate(slides):
            result = self._show_slide(
                slide.get("heading", ""),
                slide.get("text", ""),
                prompt_text,
                is_last=(i == len(slides) - 1),
            )
            if result == "skip":
                return "skip"

        return "done"

    def _show_title(self, title: str, prompt: str) -> str:
        """Показывает экран заголовка с fade-in."""
        alpha    = 0
        hold_ms  = 0
        fading   = True
        done     = False

        while not done:
            dt = self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "skip"
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE,):
                        return "skip"
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        done = True
                if event.type == pygame.MOUSEBUTTONDOWN:
                    done = True

            if fading:
                alpha = min(255, alpha + int(255 * dt / SLIDE_FADE_MS))
                if alpha >= 255:
                    fading = False

            if not fading:
                hold_ms += dt
                if AUTO_ADVANCE and hold_ms >= SLIDE_HOLD_MS:
                    done = True

            self._draw_bg()
            surf = pygame.Surface((self._W, self._H), pygame.SRCALPHA)
            t = self._font_title.render(title, True, C_TITLE)
            t.set_alpha(alpha)
            surf.blit(t, t.get_rect(centerx=self._W // 2, centery=self._H // 2 - 30))

            p = self._font_prompt.render(prompt, True, C_PROMPT)
            p.set_alpha(max(0, alpha - 100))
            surf.blit(p, p.get_rect(centerx=self._W // 2, y=self._H // 2 + 60))
            self.screen.blit(surf, (0, 0))
            pygame.display.flip()

        return "next"

    def _show_slide(self, heading: str, text: str,
                    prompt: str, is_last: bool) -> str:
        """Показывает один текстовый слайд с fade-in."""
        alpha   = 0
        hold_ms = 0
        fading  = True
        done    = False

        max_text_w = min(900, self._W - 120)
        lines = _wrap_text(text, self._font_body, max_text_w)

        while not done:
            dt = self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "skip"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return "skip"
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        done = True
                if event.type == pygame.MOUSEBUTTONDOWN:
                    done = True

            if fading:
                alpha = min(255, alpha + int(255 * dt / SLIDE_FADE_MS))
                if alpha >= 255:
                    fading = False

            if not fading:
                hold_ms += dt
                if AUTO_ADVANCE and hold_ms >= SLIDE_HOLD_MS:
                    done = True

            self._draw_bg()

            cy = self._H // 2 - (len(lines) * 30 + 60) // 2

            if heading:
                h = self._font_heading.render(heading, True, C_HEADING)
                h.set_alpha(alpha)
                self.screen.blit(h, h.get_rect(centerx=self._W // 2, y=cy))
                cy += 54

            for line in lines:
                l = self._font_body.render(line, True, C_TEXT)
                l.set_alpha(alpha)
                self.screen.blit(l, l.get_rect(centerx=self._W // 2, y=cy))
                cy += 32

            final_prompt = prompt if is_last else "Нажми ПРОБЕЛ чтобы продолжить"
            p = self._font_prompt.render(final_prompt, True, C_PROMPT)
            p.set_alpha(max(0, alpha - 80))
            self.screen.blit(p, p.get_rect(
                centerx=self._W // 2, y=self._H - 60))

            pygame.display.flip()

        return "next"

    def _draw_bg(self):
        """Рисует фон со звёздами."""
        self.screen.fill(C_BG)
        for sx, sy, r, a in self._stars:
            pygame.draw.circle(self.screen, (*C_STAR, a), (sx, sy), r)