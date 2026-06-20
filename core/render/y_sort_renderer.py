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

ВАЖНО про точку сортировки игрока:
  У игрока ДВА прямоугольника с разным назначением (см. core/player.py):
    - player.hitbox    — маленький, привязан к ногам, нужен только для
                          коллизий со стенами и боевой логики.
    - player.body_rect — полный визуальный силуэт спрайта (выше и шире
                          hitbox, т.к. персонаж выше своих ног).
  Сортировка ведётся по player.body_rect.bottom — нижней точке ИМЕННО ТОГО
  прямоугольника, который реально рисуется целиком (весь спрайт), а не по
  hitbox.bottom (иначе объект карты, чей y_sort_key попадает между
  hitbox.bottom и верхней границей спрайта, перекрывал бы только часть
  игрока — «торчала голова»).

ВАЖНО про крупные многотайловые объекты карты (исправлено):
  Объектный слой в Tiled часто содержит не только мелкие 1-2-тайловые
  декорации, но и КРУПНЫЕ объекты на много тайлов (монументы, постройки,
  декоративные композиции). Если сортировать ПОТАЙЛОВО — у каждого тайла
  свой y_sort_key — крупный объект «разваливается»: верхние тайлы считаются
  «дальше» игрока, нижние — «ближе», и персонаж оказывается разрезан
  пополам относительно объекта (видна только часть, например ноги/хитбокс,
  торс и голова «тонут» под объектом).

  Поэтому game_map.iter_object_sprites() группирует тайлы одного объектного
  слоя в связные блоки (flood fill) ещё на уровне core/map.py и отдаёт сюда
  уже ГОТОВЫЕ ГРУППЫ — каждая со своим единым y_sort_key (нижний край самого
  нижнего тайла группы). Этот рендерер просто рисует все тайлы группы одним
  блоком в момент, когда до неё доходит очередь сортировки — без какой-либо
  дополнительной группировки на своей стороне.

Контракт game_map.iter_object_sprites():
    Возвращает список (y_sort_key, [(tile_surface, world_x, world_y), ...]),
    где каждый элемент списка — одна связная группа тайлов с общим
    y_sort_key. tile_surface — уже МАСШТАБИРОВАННЫЙ Surface (под размер
    тайла на экране), готовый к прямому screen.blit() без дополнительной
    трансформации.

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

        # «Высокие» тайлы карты, уже сгруппированные в связные блоки
        # (деревья, постройки, мосты, крупные многотайловые декорации) —
        # см. core/map.py:_build_object_groups. Каждая группа — один
        # элемент сортировки с единым y_sort_key.
        for y_sort_key, tile_group in game_map.iter_object_sprites():
            entries.append((y_sort_key, "tile_group", tile_group))

        # Игрок — сортируем по нижней точке ПОЛНОГО визуального силуэта
        # (body_rect), а не узкого hitbox у ног. См. докстринг модуля.
        entries.append((float(player.body_rect.bottom), "player", player))

        # Слаймы
        for slime in slimes.enemies:
            entries.append((float(slime.rect.bottom), "slime", slime))

        # Дальние враги
        for enemy in ranged.enemies:
            entries.append((float(enemy.rect.bottom), "ranged", enemy))

        # Сортируем по Y нижней точки: меньше Y — дальше (рисуется раньше)
        entries.sort(key=lambda e: e[0])

        for _, kind, payload in entries:
            if kind == "tile_group":
                # Тайлы уже масштабированы вызывающей стороной (CachedTileMap
                # кэширует именно отмасштабированные Surface), повторное
                # масштабирование здесь не требуется и не выполняется.
                # Рисуем ВСЕ тайлы группы одним блоком — порядок внутри
                # группы не важен, т.к. они делят единый y_sort_key и
                # визуально образуют один объект.
                for tile_image, world_x, world_y in payload:
                    screen.blit(tile_image, (world_x - camera_x, world_y - camera_y))
            elif kind == "player":
                self._player_renderer.draw(screen, camera_x, camera_y)
                self._player_renderer.draw_iframe_flash(screen, camera_x, camera_y)
            elif kind == "slime":
                self._slime_renderer.draw_one(payload, screen, camera_x, camera_y)
            elif kind == "ranged":
                self._ranged_renderer.draw_one(payload, screen, camera_x, camera_y)