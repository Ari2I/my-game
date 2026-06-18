"""
tests/test_slime_fsm.py — тесты машины состояний слайма.

pygame.Rect не требует инициализации дисплея — тесты работают headless.
Для тестов используется mock-объект игрока с атрибутом hitbox.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()

import pytest
from core.slime import Slime, State, DETECT_RANGE, PREPARE_RANGE, ATTACK_RANGE


# ─── Mock-объект игрока для тестов ────────────────────────────────────────────

class MockPlayer:
    """Минимальный mock игрока с hitbox и take_damage."""

    def __init__(self, x: float = 0, y: float = 0):
        self.hitbox    = pygame.Rect(int(x) - 14, int(y) - 14, 28, 28)
        self._damage_taken: list[float] = []
        self._iframe_cd: float = 0.0

    def move_to(self, x: float, y: float):
        self.hitbox.center = (int(x), int(y))

    def take_damage(self, amount: float):
        if self._iframe_cd <= 0:
            self._damage_taken.append(amount)
            self._iframe_cd = 0.65

    @property
    def total_damage_taken(self) -> float:
        return sum(self._damage_taken)

    @property
    def hit_count(self) -> int:
        return len(self._damage_taken)


def make_slime(x=500.0, y=500.0, wave=1) -> Slime:
    """Создаёт слайма в заданной позиции."""
    return Slime(x, y, wave=wave)


MAP_W, MAP_H = 10000, 10000   # большая карта — слайм не упрётся в стену
DT = 1.0                       # 1 тик = 1/60 секунды


# ─── Тесты начального состояния ──────────────────────────────────────────────

class TestSlimeInitialState:

    def test_starts_in_wander_state(self):
        """Слайм создаётся в состоянии WANDER."""
        slime = make_slime()
        assert slime.state == State.WANDER

    def test_starts_alive(self):
        """Слайм создаётся живым с полным HP."""
        slime = make_slime()
        assert slime.alive is True
        assert slime.hp == slime.max_hp

    def test_wave_scaling_hp(self):
        """HP слайма масштабируется с волной."""
        s1 = make_slime(wave=1)
        s2 = make_slime(wave=2)
        assert s2.max_hp > s1.max_hp

    def test_initial_position(self):
        """Позиция слайма совпадает с заданной при создании."""
        slime = make_slime(x=300.0, y=400.0)
        assert abs(slime.x - 300.0) < 1e-6
        assert abs(slime.y - 400.0) < 1e-6


# ─── Тесты переходов состояний ───────────────────────────────────────────────

class TestSlimeFSMTransitions:

    def _tick(self, slime, player, n=1):
        """Симулируем n тиков обновления."""
        for _ in range(n):
            slime.update(player, DT, MAP_W, MAP_H, [])

    def test_switches_to_approach_when_player_in_detect_range(self):
        """Слайм переходит в APPROACH когда игрок в DETECT_RANGE."""
        slime  = make_slime(x=500, y=500)
        player = MockPlayer(x=500 + DETECT_RANGE - 10, y=500)

        # Несколько тиков чтобы FSM успела среагировать
        self._tick(slime, player, n=5)
        assert slime.state == State.APPROACH

    def test_stays_wander_when_player_far(self):
        """Слайм остаётся в WANDER когда игрок за пределами DETECT_RANGE."""
        slime  = make_slime(x=500, y=500)
        player = MockPlayer(x=500 + DETECT_RANGE + 100, y=500)

        self._tick(slime, player, n=10)
        assert slime.state == State.WANDER

    def test_enters_prepare_when_very_close(self):
        """Слайм переходит в PREPARE при расстоянии <= PREPARE_RANGE."""
        slime  = make_slime(x=500, y=500)
        # Ставим игрока почти вплотную
        player = MockPlayer(x=500 + PREPARE_RANGE - 5, y=500)

        # Принудительно переводим в APPROACH
        slime._enter(State.APPROACH)
        self._tick(slime, player, n=5)
        assert slime.state in (State.PREPARE, State.LUNGE, State.ATTACK)

    def test_wander_resumes_when_player_leaves(self):
        """Слайм возвращается в WANDER если игрок уходит далеко."""
        slime  = make_slime(x=500, y=500)
        player = MockPlayer(x=500 + DETECT_RANGE - 50, y=500)

        # Сначала замечаем игрока
        slime._enter(State.APPROACH)
        # Теперь игрок ушёл очень далеко
        player.move_to(500 + DETECT_RANGE * 2, 500)
        self._tick(slime, player, n=5)
        assert slime.state == State.WANDER


# ─── Тесты получения урона ────────────────────────────────────────────────────

class TestSlimeTakeDamage:

    def test_takes_damage_reduces_hp(self):
        """take_damage уменьшает HP слайма."""
        slime = make_slime()
        initial_hp = slime.hp
        slime.take_damage(10)
        assert slime.hp == initial_hp - 10

    def test_takes_damage_enters_stunned(self):
        """После получения урона слайм входит в STUNNED."""
        slime = make_slime()
        slime.take_damage(5)
        assert slime.state == State.STUNNED

    def test_hit_flash_activated(self):
        """hit_flash активируется при получении урона."""
        slime = make_slime()
        slime.take_damage(5)
        assert slime.hit_flash > 0

    def test_dies_when_hp_reaches_zero(self):
        """Слайм умирает когда HP достигает нуля."""
        slime = make_slime()
        slime.take_damage(slime.max_hp)
        assert slime.alive is False
        assert slime.hp == 0
        assert slime.state == State.DEAD

    def test_overkill_damage_does_not_go_negative(self):
        """Урон, превышающий HP, не уводит HP в отрицательные значения."""
        slime = make_slime()
        slime.take_damage(slime.max_hp * 10)
        assert slime.hp == 0

    def test_dead_slime_ignores_further_damage(self):
        """Мёртвый слайм не получает повторный урон."""
        slime = make_slime()
        slime.take_damage(slime.max_hp)
        hp_after_death = slime.hp
        slime.take_damage(100)
        assert slime.hp == hp_after_death


# ─── Тесты on_death ───────────────────────────────────────────────────────────

class TestSlimeOnDeath:

    def test_on_death_gives_xp(self):
        """on_death начисляет игроку опыт."""
        import unittest.mock as mock
        player = mock.MagicMock()
        player.inventory = mock.MagicMock()
        player.inventory.add_item = mock.MagicMock()

        slime = make_slime()
        slime.on_death(player)

        player.gain_xp.assert_called_once()
        xp_given = player.gain_xp.call_args[0][0]
        assert xp_given > 0

    def test_on_death_gives_inventory_item(self):
        """on_death добавляет предмет в инвентарь (с вероятностью ≥ 90%)."""
        import unittest.mock as mock
        import random

        # Фиксируем random чтобы loot точно выпал (slime_goo = 70% веса)
        random.seed(0)

        player = mock.MagicMock()
        player.inventory = mock.MagicMock()
        player.inventory.add_item = mock.MagicMock()

        # Вызываем много раз — хотя бы раз что-то должно выпасть
        any_item = False
        for _ in range(20):
            slime = make_slime()
            slime.on_death(player)
            if player.inventory.add_item.called:
                any_item = True
                break
        assert any_item, "on_death ни разу не выдал предмет за 20 попыток"


# ─── Тесты разделения ────────────────────────────────────────────────────────

class TestSlimeSeparation:

    def test_slimes_separate_when_overlapping(self):
        """Два перекрывающихся слайма расходятся после update."""
        s1 = make_slime(x=500, y=500)
        s2 = make_slime(x=505, y=500)   # почти на одном месте
        player = MockPlayer(x=9000, y=9000)   # далеко

        # Несколько тиков
        for _ in range(10):
            s1.update(player, DT, MAP_W, MAP_H, [s2])
            s2.update(player, DT, MAP_W, MAP_H, [s1])

        import math
        dist = math.hypot(s1.x - s2.x, s1.y - s2.y)
        assert dist > 5, f"Слаймы не разошлись: дистанция {dist:.1f}px"