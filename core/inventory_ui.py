"""
core/inventory_ui.py — панель инвентаря игрока.

Отображает все предметы из Inventory.items.
Открывается/закрывается по клавише TAB в main.py.

Принцип SRP: только отрисовка инвентаря, никакой игровой логики.
Принцип OCP: добавление нового предмета не требует правок в этом файле —
достаточно добавить его в Inventory.items.
"""

import pygame

# ─── Цвета ────────────────────────────────────────────────────────────────────
C_BG = (18, 22, 35, 230)
C_BORDER = (60, 55, 40, 255)
C_TITLE = (180, 140, 70)
C_ITEM_BG = (28, 34, 50)
C_ITEM_HOV = (40, 50, 75)
C_TEXT = (220, 210, 190)
C_DIM = (110, 100, 85)
C_ICON = (120, 200, 80)

# ─── Константы иконок предметов ──────────────────────────────────────────────
ITEM_ICONS: dict[str, str] = {
    "slime_goo": "",
    "rare_slime_goo": "",
    "magic_shard": "",
    "rune_stone": "",
}
ITEM_NAMES: dict[str, str] = {
    "slime_goo": "Слизь слайма",
    "rare_slime_goo": "Редкая слизь",
    "magic_shard": "Магический осколок",
    "rune_stone": "Рунный камень",
}

# ─── Размеры панели ───────────────────────────────────────────────────────────
PANEL_W = 420
PANEL_H = 480
ITEM_H = 52
PADDING = 16


class InventoryPanel:
    """
    Панель инвентаря.

    Использование в main.py:
        inv_panel = InventoryPanel(screen_w, screen_h)
        inv_panel.visible = not inv_panel.visible   # по TAB
        inv_panel.draw(screen, player.inventory)
    """

    def __init__(self, screen_w: int, screen_h: int):
        self.visible = False

        # Позиция: правый верхний угол экрана с отступом
        self._x = screen_w - PANEL_W - 20
        self._y = 20
        self._rect = pygame.Rect(self._x, self._y, PANEL_W, PANEL_H)

        self._font_title = pygame.font.SysFont(None, 30)
        self._font_item = pygame.font.SysFont(None, 24)
        self._font_count = pygame.font.SysFont(None, 28)
        self._font_hint = pygame.font.SysFont(None, 20)

        self._panel_surf = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
        self._scroll = 0  # для будущего скролла

    def toggle(self):
        self.visible = not self.visible

    def draw(self, screen: pygame.Surface, inventory):
        """
        Рисует панель инвентаря поверх экрана.
        inventory — объект core.player.Inventory.
        """
        if not self.visible:
            return

        surf = self._panel_surf
        surf.fill((0, 0, 0, 0))

        # Фон
        pygame.draw.rect(surf, C_BG, (0, 0, PANEL_W, PANEL_H), border_radius=10)
        pygame.draw.rect(surf, C_BORDER, (0, 0, PANEL_W, PANEL_H),
                         width=1, border_radius=10)

        # Заголовок
        title = self._font_title.render("Инвентарь", True, C_TITLE)
        surf.blit(title, (PADDING, PADDING))
        pygame.draw.line(surf, (60, 55, 40),
                         (PADDING, PADDING + 32),
                         (PANEL_W - PADDING, PADDING + 32), 1)

        items = inventory.items

        if not items:
            empty = self._font_item.render("Инвентарь пуст", True, C_DIM)
            surf.blit(empty, empty.get_rect(
                centerx=PANEL_W // 2, centery=PANEL_H // 2))
        else:
            y_off = PADDING + 44
            for item_name, count in items.items():
                if count <= 0:
                    continue
                if y_off + ITEM_H > PANEL_H - PADDING:
                    more = self._font_hint.render("ещё предметы...", True, C_DIM)
                    surf.blit(more, (PADDING, PANEL_H - PADDING - 18))
                    break

                # Фон строки предмета
                item_rect = pygame.Rect(PADDING, y_off, PANEL_W - PADDING * 2, ITEM_H - 4)
                pygame.draw.rect(surf, C_ITEM_BG, item_rect, border_radius=6)
                pygame.draw.rect(surf, (50, 48, 38), item_rect, width=1, border_radius=6)

                # Иконка
                icon = ITEM_ICONS.get(item_name, "")
                icon_s = self._font_count.render(icon, True, C_ICON)
                surf.blit(icon_s, (PADDING + 8, y_off + (ITEM_H - 4) // 2 - icon_s.get_height() // 2))

                # Название предмета
                display_name = ITEM_NAMES.get(item_name, item_name.replace("_", " ").title())
                name_s = self._font_item.render(display_name, True, C_TEXT)
                surf.blit(name_s, (PADDING + 40, y_off + 8))

                # Описание/подпись
                desc = self._font_hint.render(
                    self._item_description(item_name), True, C_DIM)
                surf.blit(desc, (PADDING + 40, y_off + 28))

                # Количество (справа)
                count_s = self._font_count.render(f"×{count}", True, C_TITLE)
                surf.blit(count_s, count_s.get_rect(
                    right=PANEL_W - PADDING - 8,
                    centery=y_off + (ITEM_H - 4) // 2,
                ))

                y_off += ITEM_H

        # Подсказка снизу
        hint = self._font_hint.render("TAB — закрыть инвентарь", True, C_DIM)
        surf.blit(hint, hint.get_rect(
            centerx=PANEL_W // 2, y=PANEL_H - PADDING - 14))

        screen.blit(surf, (self._x, self._y))

    @staticmethod
    def _item_description(item_name: str) -> str:
        """Краткое описание предмета для отображения в панели."""
        descriptions = {
            "slime_goo": "Выпадает из слаймов. Используется в крафте.",
            "rare_slime_goo": "Редкий материал. Ценится у алхимиков.",
            "magic_shard": "Осколок магического кристалла.",
            "rune_stone": "Древний камень с рунической надписью.",
        }
        return descriptions.get(item_name, "Неизвестный предмет.")
