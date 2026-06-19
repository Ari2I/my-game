"""
core/loot.py — система выпадения предметов (drop table).

«Лёгкий» алгоритм: взвешенный случайный выбор из таблицы.
Сложность O(n) по числу предметов в таблице.

Пример использования:
    item = roll_loot(SLIME_LOOT_TABLE)
    if item == "slime_goo":
        player.inventory.add_item("slime_goo", 1)
    elif item is None:
        pass  # ничего не выпало
"""

import random


def roll_loot(table: dict[str, float]) -> str | None:
    """
    Взвешенный случайный выбор предмета из таблицы.

    Args:
        table: словарь {название_предмета: вес}.
               Сумма весов не обязана равняться 1 — нормируется автоматически.
               Специальный ключ None (или отсутствие) означает «ничего».

    Returns:
        Название выбранного предмета или None, если ничего не выпало.

    Алгоритм:
        1. Суммируем все веса.
        2. Берём случайное число от 0 до суммы.
        3. Идём по таблице, вычитая каждый вес, пока не «упадём» в нужный диапазон.
    """
    if not table:
        return None

    total = sum(table.values())
    if total <= 0:
        return None

    roll = random.uniform(0.0, total)
    cumulative = 0.0
    for item, weight in table.items():
        cumulative += weight
        if roll <= cumulative:
            return item

    # Страховка от погрешностей float
    return list(table.keys())[-1]


# ─── Таблицы лута для врагов ──────────────────────────────────────────────────

# Слайм: 70% — слизь, 20% — редкая слизь, 10% — ничего не выпадает
SLIME_LOOT_TABLE: dict[str, float] = {
    "slime_goo": 70.0,
    "rare_slime_goo": 20.0,
    "nothing": 10.0,
}

# Дальний враг: 60% — магический осколок, 25% — руна, 15% — ничего
RANGED_ENEMY_LOOT_TABLE: dict[str, float] = {
    "magic_shard": 60.0,
    "rune_stone": 25.0,
    "nothing": 15.0,
}
