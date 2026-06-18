"""
tests/test_player_stats.py — тесты для классов Stats и Inventory.

Не требуют pygame.display — тестируем чистые модели данных.
"""

import sys
import os

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Мокаем pygame.image.load чтобы избежать инициализации дисплея при импорте
import unittest.mock as mock
import pygame
# Инициализируем только pygame без дисплея (для pygame.Rect и т.д.)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame.init()

from core.player import (
    Stats, Inventory,
    BASE_HP, HP_PER_POINT,
    BASE_SPEED, SPEED_PER_POINT,
    BASE_DAMAGE, DAMAGE_PER_POINT,
    STAT_POINTS_PER_LEVEL,
)


# ─── Тесты Stats ─────────────────────────────────────────────────────────────

class TestStats:

    def test_default_values(self):
        """Начальные значения характеристик равны нулю, очков нет."""
        s = Stats()
        assert s.vitality    == 0
        assert s.power       == 0
        assert s.agility     == 0
        assert s.free_points == 0

    def test_max_hp_base(self):
        """При vitality=0 max_hp равен BASE_HP."""
        s = Stats()
        assert s.max_hp() == BASE_HP

    def test_max_hp_increases_with_vitality(self):
        """Каждое очко vitality увеличивает max_hp на HP_PER_POINT."""
        s = Stats()
        s.vitality = 3
        assert s.max_hp() == BASE_HP + 3 * HP_PER_POINT

    def test_max_hp_formula_exact(self):
        """Проверяем точную формулу для произвольных значений."""
        s = Stats()
        for vit in (0, 1, 5, 10):
            s.vitality = vit
            expected   = BASE_HP + vit * HP_PER_POINT
            assert s.max_hp() == expected, (
                f"max_hp({vit}) == {s.max_hp()}, ожидалось {expected}"
            )

    def test_speed_base(self):
        """При agility=0 speed равна BASE_SPEED."""
        s = Stats()
        assert s.speed() == BASE_SPEED

    def test_speed_and_damage_formulas(self):
        """Формулы скорости и урона корректны."""
        s = Stats()
        s.agility = 4
        s.power   = 3
        assert abs(s.speed()  - (BASE_SPEED  + 4 * SPEED_PER_POINT))  < 1e-9
        assert s.damage() == BASE_DAMAGE + 3 * DAMAGE_PER_POINT

    def test_add_point_decreases_free_points(self):
        """add_point уменьшает free_points на 1."""
        s = Stats()
        s.free_points = 3
        result = s.add_point("vitality")
        assert result is True
        assert s.free_points == 2
        assert s.vitality    == 1

    def test_add_point_returns_false_without_free_points(self):
        """add_point возвращает False если очков нет."""
        s = Stats()
        s.free_points = 0
        result = s.add_point("power")
        assert result is False
        assert s.power == 0

    def test_add_point_invalid_stat(self):
        """add_point возвращает False для неизвестной характеристики."""
        s = Stats()
        s.free_points = 2
        result = s.add_point("unknown_stat")
        assert result is False
        assert s.free_points == 2   # очки не потрачены

    def test_add_point_all_stats(self):
        """Все три характеристики принимаются корректно."""
        s = Stats()
        s.free_points = 10
        for stat in ("vitality", "power", "agility"):
            before = getattr(s, stat)
            assert s.add_point(stat) is True
            assert getattr(s, stat) == before + 1

    def test_serialization_roundtrip(self):
        """to_dict / from_dict сохраняют и восстанавливают все поля."""
        s = Stats()
        s.vitality = 2; s.power = 5; s.agility = 3; s.free_points = 7
        data = s.to_dict()

        s2 = Stats()
        s2.from_dict(data)
        assert s2.vitality    == 2
        assert s2.power       == 5
        assert s2.agility     == 3
        assert s2.free_points == 7

    def test_from_dict_missing_keys(self):
        """from_dict корректно обрабатывает неполный словарь (defaults = 0)."""
        s = Stats()
        s.from_dict({})
        assert s.vitality    == 0
        assert s.power       == 0
        assert s.agility     == 0
        assert s.free_points == 0


# ─── Тесты Inventory ─────────────────────────────────────────────────────────

class TestInventory:

    def test_default_empty(self):
        """Инвентарь по умолчанию пустой."""
        inv = Inventory()
        assert inv.items == {}
        assert inv.slime_goo == 0

    def test_add_item_new(self):
        """add_item создаёт новый предмет."""
        inv = Inventory()
        inv.add_item("slime_goo", 3)
        assert inv.get_item("slime_goo") == 3

    def test_add_item_accumulates(self):
        """add_item суммирует количество одного предмета."""
        inv = Inventory()
        inv.add_item("magic_shard", 2)
        inv.add_item("magic_shard", 5)
        assert inv.get_item("magic_shard") == 7

    def test_get_item_missing(self):
        """get_item возвращает 0 для отсутствующего предмета."""
        inv = Inventory()
        assert inv.get_item("nonexistent") == 0

    def test_slime_goo_property_compat(self):
        """Свойство slime_goo совместимо с add_item."""
        inv = Inventory()
        inv.slime_goo = 5
        assert inv.slime_goo == 5
        assert inv.get_item("slime_goo") == 5

    def test_slime_goo_setter_via_property(self):
        """Сеттер slime_goo обновляет items."""
        inv = Inventory()
        inv.slime_goo = 10
        inv.add_item("slime_goo", 3)
        assert inv.slime_goo == 13

    def test_serialization_roundtrip(self):
        """to_dict / from_dict сохраняют и восстанавливают все предметы."""
        inv = Inventory()
        inv.add_item("slime_goo",   4)
        inv.add_item("magic_shard", 2)
        data = inv.to_dict()

        inv2 = Inventory()
        inv2.from_dict(data)
        assert inv2.get_item("slime_goo")   == 4
        assert inv2.get_item("magic_shard") == 2

    def test_from_dict_legacy_format(self):
        """from_dict поддерживает старый формат {slime_goo: N}."""
        inv = Inventory()
        inv.from_dict({"slime_goo": 7})
        assert inv.slime_goo == 7

    def test_multiple_items(self):
        """Инвентарь корректно хранит несколько разных предметов."""
        inv = Inventory()
        inv.add_item("slime_goo",   3)
        inv.add_item("rune_stone",  1)
        inv.add_item("magic_shard", 5)
        assert len(inv.items) == 3
        assert inv.get_item("rune_stone") == 1