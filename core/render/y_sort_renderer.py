"""
core/render/y_sort_renderer.py — отрисовка с Y-сортировкой (depth sorting).

Решает задачу: персонаж должен оказываться то ПЕРЕД объектом (деревом,
стеной, мостом), то ЗА ним — в зависимости от относительной позиции
по вертикали на экране.

Принцип: вместо двух жёстко разделённых проходов «земля → игрок → объекты»
все «высокие» сущности (тайлы объектных слоёв карты, игрок, слаймы,
дальние враги) собираются в один список, сортируются по Y-координате
их «нижней точки» (точки, которой они касаются земли), и рисуются
в этом порядке. Чем меньше Y — тем раньше рисуется (тем «дальше»),
чем больше Y — тем позже (тем «ближе» к зрителю, перекрывает остальных).

Контракт game_map.iter_object_sprites():
    Возвращает список (y_sort_key, tile_surface, world_x, world_y), где
    tile_surface — уже МАСШТАБИРОВАННЫЙ Surface (под размер тайла на экране),
    готовый к прямому screen.blit() без дополнительной трансформации.

Использование в main.py:
    y_sort = YSortRenderer(player_renderer, slime_renderer, ranged_renderer)
    y_sort.draw(
        screen, camera_x, camera_y,
        game_map=game_map,
        player=player,
        slimes=slimes,
        ranged=ranged,
    )
"""


class YSortRenderer:
    """
    Координирует Y-сортированную отрисовку игрока, врагов и «высоких»
    тайлов карты (деревья, постройки, мосты).

    Не содержит собственной логики рисования конкретных сущностей —
    делегирует существующим рендерерам (PlayerRenderer, SlimeManagerRenderer,
    RangedEnemyManagerRenderer), сохраняя принцип SRP/DRY: код отрисовки
    каждой сущности остаётся в одном месте.
    """

    def __init__(self, player_renderer, slime_renderer, ranged_renderer):
        self._player_renderer = player_renderer
        self._slime_renderer = slime_renderer
        self._ranged_renderer = ranged_renderer

    def draw(self, screen, camera_x, camera_y, *,
             game_map, player, slimes, ranged):
        """
        Рисует игрока, всех живых врагов и «высокие» тайлы карты
        одним Y-отсортированным проходом.

        Ожидается, что game_map.draw_ground() уже вызван ДО этого метода —
        земля всегда рисуется первым слоем, ниже любых сущностей.
        """
        entries: list[tuple[float, str, object]] = []

        # «Высокие» тайлы карты (деревья, постройки, мосты)
        for y_sort_key, tile_image, world_x, world_y in game_map.iter_object_sprites():
            entries.append((y_sort_key, "tile", (tile_image, world_x, world_y)))

        # Игрок — сортируем по нижней точке хитбокса (ноги)
        entries.append((float(player.hitbox.bottom), "player", player))

        # Слаймы
        for slime in slimes.enemies:
            entries.append((float(slime.rect.bottom), "slime", slime))

        # Дальние враги
        for enemy in ranged.enemies:
            entries.append((float(enemy.rect.bottom), "ranged", enemy))

        # Сортируем по Y нижней точки: меньше Y — дальше (рисуется раньше)
        entries.sort(key=lambda e: e[0])

        for _, kind, payload in entries:
            if kind == "tile":
                tile_image, world_x, world_y = payload
                # Тайл уже масштабирован вызывающей стороной (CachedTileMap
                # кэширует именно отмасштабированные Surface), повторное
                # масштабирование здесь не требуется и не выполняется.
                screen.blit(tile_image, (world_x - camera_x, world_y - camera_y))
            elif kind == "player":
                self._player_renderer.draw(screen, camera_x, camera_y)
                self._player_renderer.draw_iframe_flash(screen, camera_x, camera_y)
            elif kind == "slime":
                self._slime_renderer.draw_one(payload, screen, camera_x, camera_y)
            elif kind == "ranged":
                self._ranged_renderer.draw_one(payload, screen, camera_x, camera_y)
