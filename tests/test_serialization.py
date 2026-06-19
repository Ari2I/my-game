"""
tests/test_serialization.py — тесты сериализации Stats, Inventory.

Проверяем to_dict/from_dict: сохраняем → восстанавливаем → сравниваем поля.
Не требует pygame.display — работает headless.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

import json
import pytest
from core.player import Stats, Inventory


# ─── Тесты сериализации Stats ─────────────────────────────────────────────────

class TestStatsSerializaton:

    def test_roundtrip_empty(self):
        """Пустые Stats: сохранить и восстановить — все нули."""
        s = Stats()
        s2 = Stats()
        s2.from_dict(s.to_dict())
        assert s2.vitality == 0
        assert s2.power == 0
        assert s2.agility == 0
        assert s2.free_points == 0

    def test_roundtrip_filled(self):
        """Заполненные Stats сохраняются и восстанавливаются без потерь."""
        s = Stats()
        s.vitality = 5
        s.power = 3
        s.agility = 7
        s.free_points = 2
        data = s.to_dict()

        s2 = Stats()
        s2.from_dict(data)
        assert s2.vitality == 5
        assert s2.power == 3
        assert s2.agility == 7
        assert s2.free_points == 2

    def test_to_dict_is_json_serializable(self):
        """to_dict() возвращает структуру, сериализуемую в JSON."""
        s = Stats()
        s.vitality = 4;
        s.power = 2;
        s.agility = 1;
        s.free_points = 3
        raw = json.dumps(s.to_dict())  # не должно бросать исключений
        restored = json.loads(raw)
        s2 = Stats()
        s2.from_dict(restored)
        assert s2.vitality == 4

    def test_from_dict_partial_keys(self):
        """from_dict с частичным словарём — остальные поля == 0."""
        s = Stats()
        s.from_dict({"power": 9})
        assert s.power == 9
        assert s.vitality == 0
        assert s.agility == 0
        assert s.free_points == 0

    def test_derived_values_correct_after_restore(self):
        """После восстановления вычисляемые поля (max_hp, damage) корректны."""
        from core.player import BASE_HP, HP_PER_POINT, BASE_DAMAGE, DAMAGE_PER_POINT
        s = Stats()
        s.vitality = 3;
        s.power = 4
        data = s.to_dict()

        s2 = Stats()
        s2.from_dict(data)
        assert s2.max_hp() == BASE_HP + 3 * HP_PER_POINT
        assert s2.damage() == BASE_DAMAGE + 4 * DAMAGE_PER_POINT


# ─── Тесты сериализации Inventory ────────────────────────────────────────────

class TestInventorySerialization:

    def test_roundtrip_empty(self):
        """Пустой инвентарь сохраняется и восстанавливается пустым."""
        inv = Inventory()
        inv2 = Inventory()
        inv2.from_dict(inv.to_dict())
        assert inv2.items == {}

    def test_roundtrip_multiple_items(self):
        """Несколько предметов сохраняются и восстанавливаются корректно."""
        inv = Inventory()
        inv.add_item("slime_goo", 5)
        inv.add_item("magic_shard", 2)
        inv.add_item("rune_stone", 1)
        data = inv.to_dict()

        inv2 = Inventory()
        inv2.from_dict(data)
        assert inv2.get_item("slime_goo") == 5
        assert inv2.get_item("magic_shard") == 2
        assert inv2.get_item("rune_stone") == 1

    def test_to_dict_is_json_serializable(self):
        """to_dict() возвращает JSON-сериализуемую структуру."""
        inv = Inventory()
        inv.add_item("slime_goo", 3)
        raw = json.dumps(inv.to_dict())
        data = json.loads(raw)
        inv2 = Inventory()
        inv2.from_dict(data)
        assert inv2.get_item("slime_goo") == 3

    def test_legacy_format_backwards_compat(self):
        """Старый формат {slime_goo: N} читается корректно."""
        inv = Inventory()
        inv.from_dict({"slime_goo": 7})
        assert inv.slime_goo == 7
        assert inv.get_item("slime_goo") == 7

    def test_add_item_accumulates_and_survives_roundtrip(self):
        """Накопление предметов сохраняется через сериализацию."""
        inv = Inventory()
        inv.add_item("slime_goo", 2)
        inv.add_item("slime_goo", 3)  # итого 5
        data = inv.to_dict()

        inv2 = Inventory()
        inv2.from_dict(data)
        assert inv2.slime_goo == 5

    def test_zero_items_not_restored_as_garbage(self):
        """Предметы с количеством > 0 корректно восстанавливаются."""
        inv = Inventory()
        inv.add_item("magic_shard", 1)
        data = inv.to_dict()

        inv2 = Inventory()
        inv2.from_dict(data)
        assert inv2.get_item("nonexistent") == 0


# ─── Тесты совместной сериализации Stats + Inventory ─────────────────────────

class TestCombinedSerialization:

    def _make_save(self, vitality=2, power=1, agility=3,
                   free=0, items=None) -> dict:
        """Создаёт словарь сохранения как это делает Player.to_dict."""
        s = Stats()
        s.vitality = vitality;
        s.power = power
        s.agility = agility;
        s.free_points = free

        inv = Inventory()
        for name, count in (items or {}).items():
            inv.add_item(name, count)

        return {
            "x": 100.0, "y": 200.0,
            "level": 3, "xp": 75,
            "current_hp": 80.0,
            "stats": s.to_dict(),
            "inventory": inv.to_dict(),
        }

    def test_full_save_roundtrip(self):
        """Полное сохранение: Stats + Inventory восстанавливаются без потерь."""
        save = self._make_save(
            vitality=4, power=2, agility=1, free=3,
            items={"slime_goo": 5, "magic_shard": 1},
        )
        raw = json.dumps(save)
        data = json.loads(raw)

        # Восстанавливаем Stats
        s2 = Stats()
        s2.from_dict(data["stats"])
        assert s2.vitality == 4
        assert s2.power == 2
        assert s2.agility == 1
        assert s2.free_points == 3

        # Восстанавливаем Inventory
        inv2 = Inventory()
        inv2.from_dict(data["inventory"])
        assert inv2.get_item("slime_goo") == 5
        assert inv2.get_item("magic_shard") == 1

        # Прочие поля
        assert data["level"] == 3
        assert data["xp"] == 75
        assert abs(data["current_hp"] - 80.0) < 1e-9

    def test_save_is_stable_under_multiple_roundtrips(self):
        """Многократная сериализация не искажает данные."""
        save = self._make_save(vitality=5, items={"rune_stone": 2})

        # Два прохода сериализации
        data = json.loads(json.dumps(json.loads(json.dumps(save))))

        s2 = Stats()
        s2.from_dict(data["stats"])
        assert s2.vitality == 5

        inv2 = Inventory()
        inv2.from_dict(data["inventory"])
        assert inv2.get_item("rune_stone") == 2
