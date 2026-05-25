import pygame


class Map:
    def __init__(self, screen_width, screen_height, tile_size=64):
        self.tile_size = tile_size
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Рассчитываем размер карты в тайлах
        self.map_width = screen_width // tile_size
        self.map_height = screen_height // tile_size

        # Загружаем спрайты
        self.ground_sprites = self._load_tileset('images/PNG/Ground.png', tile_size)
        self.water_sprites = self._load_tileset('images/PNG/Water_coasts.png', tile_size)
        self.object_sprites = self._load_tileset('images/PNG/Objects.png', tile_size)
        self.spot_sprites = self._load_tileset('images/PNG/spots.png', tile_size)

        # Создаём карту уровня
        self.level_map = []
        self.enemy_spawns = []
        self._generate_island_level()

    def _load_tileset(self, path, tile_size):
        """Загружает тайлсет и разбивает на отдельные тайлы"""
        image = pygame.image.load(path).convert_alpha()
        tiles = []

        for y in range(0, image.get_height(), tile_size):
            for x in range(0, image.get_width(), tile_size):
                if x + tile_size <= image.get_width() and y + tile_size <= image.get_height():
                    tile = image.subsurface((x, y, tile_size, tile_size))
                    tiles.append(tile)

        return tiles

    def _generate_island_level(self):
        """Генерирует уровень с островом посередине, окружённым водой"""
        self.level_map = []
        self.enemy_spawns = []

        # Определяем границы острова
        island_margin = 2  # Количество тайлов воды по краям
        island_inner_margin = 4  # Внутренняя граница для спавна в центре

        for row in range(self.map_height):
            level_row = []
            for col in range(self.map_width):
                # Проверяем, находится ли тайл на краю (вода)
                is_edge = (row < island_margin or
                          row >= self.map_height - island_margin or
                          col < island_margin or
                          col >= self.map_width - island_margin)

                # Проверяем, находится ли тайл внутри острова
                is_island = not is_edge

                if is_edge:
                    # Вода по краям - используем первый тайл из water_sprites
                    tile_index = 0 if self.water_sprites else 0
                    level_row.append(('water', tile_index))

                    # Добавляем точки спавна по краям
                    if (row == island_margin or row == self.map_height - island_margin - 1 or
                        col == island_margin or col == self.map_width - island_margin - 1):
                        if len(self.enemy_spawns) < 8:  # Максимум 8 спавнов по краям
                            self.enemy_spawns.append((col * self.tile_size, row * self.tile_size))
                else:
                    # Земля острова - используем первый тайл из ground_sprites
                    tile_index = 0 if self.ground_sprites else 0
                    level_row.append(('ground', tile_index))

            self.level_map.append(level_row)

        # Добавляем центральный спавн
        center_x = (self.map_width // 2) * self.tile_size
        center_y = (self.map_height // 2) * self.tile_size
        self.enemy_spawns.append((center_x, center_y))

    def draw(self, screen, camera_x=0, camera_y=0):
        """Отрисовывает карту на экране"""
        for row in range(len(self.level_map)):
            for col in range(len(self.level_map[row])):
                tile_type, tile_index = self.level_map[row][col]

                # Вычисляем позицию на экране с учётом камеры
                screen_x = col * self.tile_size - camera_x
                screen_y = row * self.tile_size - camera_y

                # Отрисовываем только видимые тайлы
                if (-self.tile_size < screen_x < self.screen_width and
                    -self.tile_size < screen_y < self.screen_height):

                    if tile_type == 'water' and self.water_sprites:
                        sprite = self.water_sprites[tile_index % len(self.water_sprites)]
                        screen.blit(sprite, (screen_x, screen_y))
                    elif tile_type == 'ground' and self.ground_sprites:
                        sprite = self.ground_sprites[tile_index % len(self.ground_sprites)]
                        screen.blit(sprite, (screen_x, screen_y))

    def get_enemy_spawns(self):
        """Возвращает список точек спавна противников"""
        return self.enemy_spawns

    def draw_spawn_points(self, screen, camera_x=0, camera_y=0):
        """Отрисовывает точки спавна для отладки"""
        if self.spot_sprites and len(self.spot_sprites) > 0:
            spot_sprite = self.spot_sprites[0]
            for spawn_x, spawn_y in self.enemy_spawns:
                screen_x = spawn_x - camera_x
                screen_y = spawn_y - camera_y
                if (-self.tile_size < screen_x < self.screen_width and
                    -self.tile_size < screen_y < self.screen_height):
                    screen.blit(spot_sprite, (screen_x, screen_y))


# Для обратной совместимости
def load_tiles(path, tile_size):
    image = pygame.image.load(path).convert_alpha()
    tiles = []

    for y in range(0, image.get_height(), tile_size):
        for x in range(0, image.get_width(), tile_size):
            if x + tile_size <= image.get_width() and y + tile_size <= image.get_height():
                tile = image.subsurface((x, y, tile_size, tile_size))
                tiles.append(tile)

    return tiles