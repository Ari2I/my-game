"""
tests/test_save_system.py — тесты сохранения/загрузки прогресса.

Проверяет core/save_system.py: создание новых слотов, перезапись текущего
слота при повторном сохранении той же партии, список сохранений, чтение,
удаление и поведение при переполнении лимита слотов.

Не требует pygame.display — save_system.py не зависит от pygame вообще.
"""

import sys
import os
import shutil
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()

import pytest
import core.save_system as ss


class FakePlayer:
    """Минимальная заглушка игрока — достаточно to_dict() с нужными полями."""

    def __init__(self, level=1):
        self.level = level

    def to_dict(self):
        return {
            "x": 100.0, "y": 200.0,
            "level": self.level, "xp": 50,
            "current_hp": 80.0,
            "stats": {"vitality": 0, "power": 0, "agility": 0, "free_points": 0},
            "inventory": {"items": {"slime_goo": 2}},
        }


@pytest.fixture
def temp_saves_dir(monkeypatch):
    """Подменяет SAVES_DIR на временную директорию на время теста."""
    tmpdir = tempfile.mkdtemp()
    monkeypatch.setattr(ss, "SAVES_DIR", tmpdir)
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestSaveGame:

    def test_first_save_creates_new_slot(self, temp_saves_dir):
        """Первое сохранение партии создаёт save_1.json."""
        player = FakePlayer()
        path = ss.save_game(player, playtime_seconds=10, slot_path=None)
        assert path.endswith("save_1.json")
        assert os.path.isfile(path)

    def test_resave_same_slot_does_not_duplicate(self, temp_saves_dir):
        """Повторное сохранение той же партии перезаписывает тот же файл."""
        player = FakePlayer()
        path1 = ss.save_game(player, playtime_seconds=10, slot_path=None)
        path2 = ss.save_game(player, playtime_seconds=20, slot_path=path1)
        assert path1 == path2
        assert len(ss.list_saves()) == 1

    def test_new_game_creates_separate_slot(self, temp_saves_dir):
        """Сохранение новой партии (slot_path=None) создаёт отдельный файл."""
        player = FakePlayer()
        path1 = ss.save_game(player, playtime_seconds=10, slot_path=None)
        path2 = ss.save_game(player, playtime_seconds=10, slot_path=None)
        assert path1 != path2
        assert len(ss.list_saves()) == 2

    def test_save_file_is_valid_json_with_player_key(self, temp_saves_dir):
        """Файл сохранения — валидный JSON со вложенным player."""
        import json
        player = FakePlayer(level=5)
        path = ss.save_game(player, playtime_seconds=0, slot_path=None)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["level"] == 5
        assert "player" in data
        assert data["player"]["level"] == 5

    def test_playtime_formatted_as_hh_mm_ss(self, temp_saves_dir):
        """playtime сохраняется в формате ЧЧ:ММ:СС."""
        player = FakePlayer()
        path = ss.save_game(player, playtime_seconds=3725, slot_path=None)  # 1:02:05
        saves = ss.list_saves()
        assert saves[0]["time"] == "01:02:05"

    def test_overwrites_oldest_when_all_slots_full(self, temp_saves_dir):
        """Когда все MAX_SAVES слотов заняты, новое сохранение перезаписывает самое старое."""
        player = FakePlayer()
        paths = []
        for i in range(ss.MAX_SAVES):
            paths.append(ss.save_game(player, playtime_seconds=i, slot_path=None))
            time.sleep(0.01)  # гарантируем разные mtime

        assert len(set(paths)) == ss.MAX_SAVES
        oldest = min(paths, key=lambda p: os.path.getmtime(p))

        time.sleep(0.01)
        new_path = ss.save_game(player, playtime_seconds=999, slot_path=None)

        assert new_path == oldest
        assert len(ss.list_saves()) == ss.MAX_SAVES


class TestListSaves:

    def test_empty_when_no_saves(self, temp_saves_dir):
        """Пустая директория -> пустой список, без исключений."""
        assert ss.list_saves() == []

    def test_sorted_newest_first(self, temp_saves_dir):
        """Список сохранений отсортирован от новых к старым."""
        player = FakePlayer()
        first = ss.save_game(player, playtime_seconds=0, slot_path=None)
        time.sleep(0.01)
        second = ss.save_game(player, playtime_seconds=0, slot_path=None)

        saves = ss.list_saves()
        assert saves[0]["file"] == second
        assert saves[1]["file"] == first

    def test_corrupted_file_does_not_crash_listing(self, temp_saves_dir):
        """Повреждённый JSON-файл сохранения не ломает list_saves()."""
        bad_path = os.path.join(temp_saves_dir, "save_1.json")
        with open(bad_path, "w") as f:
            f.write("{не json вообще")

        saves = ss.list_saves()
        assert len(saves) == 1
        assert saves[0]["level"] == "—"


class TestLoadPlayerDict:

    def test_roundtrip_new_format(self, temp_saves_dir):
        """save_game -> load_player_dict восстанавливает те же данные игрока."""
        player = FakePlayer(level=7)
        path = ss.save_game(player, playtime_seconds=0, slot_path=None)

        restored = ss.load_player_dict(path)
        assert restored["level"] == 7
        assert restored["inventory"]["items"]["slime_goo"] == 2

    def test_legacy_format_without_player_key(self, temp_saves_dir):
        """Старый формат (данные игрока прямо в корне файла) тоже читается."""
        import json
        path = os.path.join(temp_saves_dir, "save_1.json")
        legacy_data = {"x": 1.0, "y": 2.0, "level": 9, "xp": 0,
                       "current_hp": 100.0, "stats": {}, "inventory": {}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        restored = ss.load_player_dict(path)
        assert restored["level"] == 9


class TestDeleteSave:

    def test_delete_removes_file(self, temp_saves_dir):
        """delete_save удаляет файл и убирает его из list_saves()."""
        player = FakePlayer()
        path = ss.save_game(player, playtime_seconds=0, slot_path=None)
        assert len(ss.list_saves()) == 1

        result = ss.delete_save(path)
        assert result is True
        assert len(ss.list_saves()) == 0
        assert not os.path.isfile(path)

    def test_delete_nonexistent_returns_false(self, temp_saves_dir):
        """Удаление несуществующего файла возвращает False, не бросает исключение."""
        fake_path = os.path.join(temp_saves_dir, "save_99.json")
        assert ss.delete_save(fake_path) is False