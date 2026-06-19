"""
core/audio.py — звуковая система.

Принцип SRP: только управление звуком, без игровой логики.
Принцип DRY: загруженные звуки кэшируются — файл читается один раз.
Принцип KISS: простая обёртка над pygame.mixer.

Ожидаемая структура файлов:
    assets/sounds/
        hit.wav          — удар по врагу
        player_hurt.wav  — урон по игроку
        enemy_hurt.wav   — урон по врагу
        music_game.ogg   — фоновая музыка игры

Если файл не найден — AudioManager молча пропускает (игра не падает).
"""

import os
import pygame

# ─── Пути к ресурсам ─────────────────────────────────────────────────────────
SOUNDS_DIR = os.path.join("assets", "sounds")

# Имена звуковых эффектов → файлы
SFX_FILES: dict[str, str] = {
    "hit": "hit.wav",
    "player_hurt": "player_hurt.wav",
    "enemy_hurt": "enemy_hurt.wav",
    "projectile": "projectile.wav",
    "level_up": "level_up.wav",
}

# Файл фоновой музыки
MUSIC_FILE = os.path.join(SOUNDS_DIR, "music_game.ogg")

# Громкость по умолчанию
DEFAULT_SFX_VOLUME = 0.7
DEFAULT_MUSIC_VOLUME = 0.4


class AudioManager:
    """
    Менеджер звука. Кэширует загруженные Sound-объекты.

    Использование:
        audio = AudioManager()
        audio.play_music()
        audio.play_sfx("hit")

    Если звуковые файлы отсутствуют — все вызовы тихо игнорируются.
    """

    def __init__(self):
        self._sfx_cache: dict[str, pygame.mixer.Sound | None] = {}
        self._sfx_volume = DEFAULT_SFX_VOLUME
        self._music_volume = DEFAULT_MUSIC_VOLUME
        self._music_playing = False

        # Проверяем, инициализирован ли mixer
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            except Exception as e:
                print(f"[AudioManager] mixer init failed: {e}")

    # ── SFX ──────────────────────────────────────────────────────────────────
    def play_sfx(self, name: str) -> None:
        """Воспроизвести звуковой эффект по имени (кэшируется)."""
        sound = self._get_sfx(name)
        if sound is not None:
            sound.play()

    def set_sfx_volume(self, volume: float) -> None:
        """Установить громкость SFX (0.0–1.0). Применяется ко всем кэшированным."""
        self._sfx_volume = max(0.0, min(1.0, volume))
        for sound in self._sfx_cache.values():
            if sound is not None:
                sound.set_volume(self._sfx_volume)

    # ── Музыка ───────────────────────────────────────────────────────────────
    def play_music(self, filename: str | None = None, loop: bool = True) -> None:
        """Запустить фоновую музыку."""
        path = filename or MUSIC_FILE
        if not os.path.isfile(path):
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self._music_volume)
            pygame.mixer.music.play(-1 if loop else 0)
            self._music_playing = True
        except Exception as e:
            print(f"[AudioManager] Не удалось загрузить музыку '{path}': {e}")

    def stop_music(self) -> None:
        pygame.mixer.music.stop()
        self._music_playing = False

    def set_music_volume(self, volume: float) -> None:
        self._music_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self._music_volume)

    # ── Внутренний загрузчик с кэшированием ──────────────────────────────────
    def _get_sfx(self, name: str) -> "pygame.mixer.Sound | None":
        """Возвращает Sound из кэша или загружает. При ошибке — None."""
        if name in self._sfx_cache:
            return self._sfx_cache[name]

        filename = SFX_FILES.get(name)
        if filename is None:
            self._sfx_cache[name] = None
            return None

        path = os.path.join(SOUNDS_DIR, filename)
        if not os.path.isfile(path):
            # Файл не найден — кэшируем None, не спамим в консоль
            self._sfx_cache[name] = None
            return None

        try:
            sound = pygame.mixer.Sound(path)
            sound.set_volume(self._sfx_volume)
            self._sfx_cache[name] = sound
            return sound
        except Exception as e:
            print(f"[AudioManager] Не удалось загрузить '{path}': {e}")
            self._sfx_cache[name] = None
            return None
