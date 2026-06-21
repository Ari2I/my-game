"""
core/save_system.py — сохранение и загрузка прогресса игрока.

Принцип SRP: этот модуль отвечает только за чтение/запись файлов
сохранений на диске (формат, имена файлов, директория). Он ничего не
знает о Player как о классе с анимацией/логикой — работает с уже
готовым словарём (player.to_dict()) и отдаёт обратно словарь для
player.from_dict(...).

Формат имени файла: save_<номер>.json (save_1.json, save_2.json, ...).
Каждый файл хранит:
    {
        "name": "Сохранение N",
        "level": <int>,
        "playtime": "ЧЧ:ММ:СС",
        "saved_at": "<ISO-дата>",
        "player": {... player.to_dict() ...}
    }

Использование:
    from core.save_system import (
        save_game, list_saves, delete_save, SAVES_DIR,
    )

    # Сохранить (создаст новый файл или перезапишет текущий слот)
    path = save_game(player, playtime_seconds=325, slot_path=None)

    # Получить список сохранений для LoadScreen
    saves = list_saves()   # -> list[dict] с ключами file/name/level/time

    # Удалить сохранение
    delete_save(path)
"""

import json
import os
import time

SAVES_DIR = "saves"
MAX_SAVES = 5  # сколько слотов сохранений поддерживается


def _ensure_dir():
    os.makedirs(SAVES_DIR, exist_ok=True)


def _format_playtime(seconds: float) -> str:
    """Переводит секунды в строку ЧЧ:ММ:СС."""
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _next_free_slot_path() -> str:
    """
    Находит первый свободный номер слота (save_1.json, save_2.json, ...)
    либо, если все MAX_SAVES слотов заняты, возвращает путь к самому
    старому по дате изменения файлу (он будет перезаписан).
    """
    _ensure_dir()
    existing = {
        f for f in os.listdir(SAVES_DIR)
        if f.startswith("save_") and f.endswith(".json")
    }

    for i in range(1, MAX_SAVES + 1):
        candidate = f"save_{i}.json"
        if candidate not in existing:
            return os.path.join(SAVES_DIR, candidate)

    # Все слоты заняты — перезаписываем самый старый
    paths = [os.path.join(SAVES_DIR, f) for f in existing]
    oldest = min(paths, key=lambda p: os.path.getmtime(p))
    return oldest


def save_game(player, playtime_seconds: float = 0.0,
              slot_path: str | None = None) -> str:
    """
    Сохраняет текущее состояние игрока в файл.

    Args:
        player: объект core.player.Player (или совместимый, с to_dict()).
        playtime_seconds: суммарное время в текущей игровой сессии,
            используется только для отображения в LoadScreen.
        slot_path: если указан — перезаписать именно этот файл (используется
            при повторном сохранении уже загруженной игры, чтобы не плодить
            новые слоты при каждом сохранении одной и той же партии).
            Если None — создаётся новый слот (или перезаписывается самый
            старый, если все MAX_SAVES слотов заняты).

    Returns:
        Путь к файлу, в который реально было записано сохранение —
        используй его как новый "текущий" slot_path для последующих
        сохранений той же партии.
    """
    _ensure_dir()

    path = slot_path if slot_path else _next_free_slot_path()

    data = {
        "name": os.path.splitext(os.path.basename(path))[0],
        "level": player.level,
        "playtime": _format_playtime(playtime_seconds),
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "player": player.to_dict(),
    }

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)  # атомарная замена — не оставит "битый" файл

    return path


def list_saves() -> list[dict]:
    """
    Возвращает список сохранений для отображения в LoadScreen, отсортированный
    по дате изменения (сначала новые).

    Каждый элемент: {"file": путь, "name": ..., "level": ..., "time": ...}
    """
    _ensure_dir()
    saves = []
    for fname in os.listdir(SAVES_DIR):
        if not fname.startswith("save_") or not fname.endswith(".json"):
            continue
        path = os.path.join(SAVES_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            saves.append({
                "file": path,
                "name": data.get("name", fname),
                "level": data.get("level", "—"),
                "time": data.get("playtime", "—"),
                "mtime": os.path.getmtime(path),
            })
        except Exception:
            # Повреждённый файл — показываем заглушкой, не роняем экран
            saves.append({
                "file": path, "name": fname,
                "level": "—", "time": "—",
                "mtime": os.path.getmtime(path) if os.path.exists(path) else 0,
            })

    saves.sort(key=lambda s: s["mtime"], reverse=True)
    return saves


def load_player_dict(path: str) -> dict:
    """
    Читает файл сохранения и возвращает словарь для player.from_dict(...).

    Поддерживает как новый формат ({"player": {...}}), так и старый
    легаси-формат, где данные игрока лежали прямо в корне файла —
    обратная совместимость со старыми сохранениями.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if "player" in data:
        return data["player"]
    return data  # легаси-формат: данные игрока в корне


def delete_save(path: str) -> bool:
    """Удаляет файл сохранения. Возвращает True при успехе."""
    try:
        os.remove(path)
        return True
    except OSError:
        return False