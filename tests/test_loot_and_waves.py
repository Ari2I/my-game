"""
tests/test_loot_and_waves.py — тесты алгоритмов лута и волн.

Проверяем корректность взвешенного выбора и логику WaveManager.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

import pytest
import random
from core.loot import roll_loot


# ─── Тесты roll_loot ─────────────────────────────────────────────────────────

class TestRollLoot:

    def test_returns_item_from_table(self):
        """Результат всегда один из ключей таблицы."""
        table = {"sword": 50.0, "shield": 30.0, "potion": 20.0}
        for _ in range(100):
            result = roll_loot(table)
            assert result in table

    def test_empty_table_returns_none(self):
        """Пустая таблица возвращает None."""
        assert roll_loot({}) is None

    def test_single_item_always_returned(self):
        """Таблица с одним предметом всегда возвращает его."""
        table = {"only_item": 1.0}
        for _ in range(20):
            assert roll_loot(table) == "only_item"

    def test_zero_weight_item_never_returned(self):
        """Предмет с весом 0 никогда не возвращается."""
        table = {"common": 100.0, "impossible": 0.0}
        results = {roll_loot(table) for _ in range(200)}
        assert "impossible" not in results

    def test_distribution_is_roughly_proportional(self):
        """Распределение примерно соответствует весам (статистический тест)."""
        random.seed(42)
        table = {"rare": 10.0, "common": 90.0}
        counts = {"rare": 0, "common": 0}
        n = 1000
        for _ in range(n):
            item = roll_loot(table)
            counts[item] += 1

        # rare должен выпасть примерно в 10% случаев (допуск ±5%)
        rare_pct = counts["rare"] / n
        assert 0.05 <= rare_pct <= 0.20, (
            f"rare выпал {rare_pct * 100:.1f}%, ожидалось ~10%"
        )

    def test_unnormalized_weights_work(self):
        """Веса не обязаны суммироваться в 1 или 100."""
        table = {"a": 3.0, "b": 7.0}
        results = [roll_loot(table) for _ in range(200)]
        assert "a" in results
        assert "b" in results

    def test_nothing_key_treated_normally(self):
        """Ключ 'nothing' — обычный предмет, не магический."""
        table = {"nothing": 50.0, "item": 50.0}
        results = set(roll_loot(table) for _ in range(50))
        # Оба должны встретиться
        assert len(results) == 2


# ─── Тесты WaveManager ───────────────────────────────────────────────────────

class TestWaveManager:
    """Тесты логики WaveManager без реальных врагов."""

    def _make_manager(self, slime_count=0, ranged_count=0):
        """Создаёт WaveManager с mock-менеджерами."""
        import unittest.mock as mock
        from core.wave_manager import WaveManager

        slime_mgr = mock.MagicMock()
        ranged_mgr = mock.MagicMock()

        # count — текущее число врагов
        slime_mgr.count = slime_count
        ranged_mgr.count = ranged_count

        wm = WaveManager(slime_mgr, ranged_mgr)
        return wm, slime_mgr, ranged_mgr

    def test_starts_at_wave_zero(self):
        """WaveManager начинает с волны 0 (ещё не начиналась)."""
        wm, _, _ = self._make_manager()
        assert wm.wave == 0

    def test_starts_in_delay(self):
        """Начальное состояние — delay (ожидание перед первой волной)."""
        wm, _, _ = self._make_manager()
        assert wm.is_between_waves is True

    def test_wave_increments_after_delay(self):
        """После WAVE_START_DELAY секунд волна инкрементируется."""
        from core.wave_manager import WAVE_START_DELAY
        wm, slime_mgr, ranged_mgr = self._make_manager()

        # Симулируем прошедшее время (dt = 60 тиков = 1 секунда)
        ticks_needed = int(WAVE_START_DELAY * 60) + 5
        for _ in range(ticks_needed):
            slime_mgr.count = 0
            ranged_mgr.count = 0
            wm.update(1.0)

        assert wm.wave == 1

    def test_spawn_called_on_wave_start(self):
        """spawn_wave вызывается при начале новой волны."""
        from core.wave_manager import WAVE_START_DELAY
        wm, slime_mgr, ranged_mgr = self._make_manager()

        ticks_needed = int(WAVE_START_DELAY * 60) + 5
        for _ in range(ticks_needed):
            slime_mgr.count = 0
            ranged_mgr.count = 0
            wm.update(1.0)

        slime_mgr.spawn_wave.assert_called_once()
        ranged_mgr.spawn_wave.assert_called_once()

    def test_enemies_remaining_property(self):
        """enemies_remaining суммирует count обоих менеджеров."""
        wm, slime_mgr, ranged_mgr = self._make_manager(
            slime_count=3, ranged_count=2)
        assert wm.enemies_remaining == 5

    def test_time_until_next_wave_decreases(self):
        """time_until_next_wave уменьшается с каждым тиком."""
        wm, _, _ = self._make_manager()
        t1 = wm.time_until_next_wave
        wm.update(60.0)  # 1 секунда
        t2 = wm.time_until_next_wave
        assert t2 < t1

    def test_next_wave_starts_after_all_enemies_die(self):
        """Следующая волна начинается когда все враги мертвы."""
        from core.wave_manager import WAVE_START_DELAY
        wm, slime_mgr, ranged_mgr = self._make_manager()

        # Запускаем первую волну
        ticks_for_delay = int(WAVE_START_DELAY * 60) + 5
        for _ in range(ticks_for_delay):
            slime_mgr.count = 0
            ranged_mgr.count = 0
            wm.update(1.0)
        assert wm.wave == 1

        # Все враги убиты, ждём вторую волну
        slime_mgr.count = 0
        ranged_mgr.count = 0
        for _ in range(ticks_for_delay):
            slime_mgr.count = 0
            ranged_mgr.count = 0
            wm.update(1.0)

        assert wm.wave == 2
