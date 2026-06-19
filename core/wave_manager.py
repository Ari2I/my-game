"""
core/wave_manager.py — управление волнами врагов.

«Лёгкий» алгоритм: таймер + счётчик волн.
Волна завершается когда все враги убиты (или истёк таймер),
после чего начинается следующая с большим числом/силой врагов.
"""

# ─── Константы волн ───────────────────────────────────────────────────────────
WAVE_START_DELAY = 3.0  # секунд паузы перед началом волны
WAVE_TIMEOUT = 120.0  # секунд до принудительной смены волны
SLIMES_PER_WAVE = 5  # базовое число слаймов в волне
RANGED_PER_WAVE = 2  # базовое число дальних врагов в волне
SLIME_SCALE_PER_WAVE = 2  # +N слаймов за каждую волну
RANGED_SCALE_PER_WAVE = 1  # +N дальних врагов за каждую волну


class WaveManager:
    """
    Контролирует последовательность волн врагов.

    Использование в main.py:
        wave_mgr = WaveManager(slime_mgr, ranged_mgr)
        ...
        wave_mgr.update(dt)  # вызывать каждый кадр

    Алгоритм:
        1. Ждём WAVE_START_DELAY секунд (между волнами).
        2. Спавним врагов текущей волны.
        3. Ждём пока все враги не умрут ИЛИ не истечёт WAVE_TIMEOUT.
        4. Переходим к следующей волне (wave += 1).
    """

    def __init__(self, slime_manager, ranged_manager):
        self.slime_mgr = slime_manager
        self.ranged_mgr = ranged_manager

        self.current_wave: int = 0  # 0 = волна ещё не начиналась
        self._timer: float = 0.0
        self._state: str = "delay"  # "delay" | "active"
        self._spawned: bool = False

    # ── обновление ────────────────────────────────────────────────────────────
    def update(self, dt: float):
        """Вызывать каждый кадр. dt — тики (60 = 1 сек)."""
        dt_sec = dt / 60.0
        self._timer += dt_sec

        if self._state == "delay":
            if self._timer >= WAVE_START_DELAY:
                self._start_next_wave()

        elif self._state == "active":
            all_dead = (self.slime_mgr.count == 0 and
                        self.ranged_mgr.count == 0)
            timed_out = self._timer >= WAVE_TIMEOUT

            if all_dead or timed_out:
                self._state = "delay"
                self._timer = 0.0

    # ── запуск волны ──────────────────────────────────────────────────────────
    def _start_next_wave(self):
        self.current_wave += 1
        self._timer = 0.0
        self._state = "active"

        slime_count = SLIMES_PER_WAVE + (self.current_wave - 1) * SLIME_SCALE_PER_WAVE
        ranged_count = RANGED_PER_WAVE + (self.current_wave - 1) * RANGED_SCALE_PER_WAVE

        self.slime_mgr.spawn_wave(wave=self.current_wave, count=slime_count)
        self.ranged_mgr.spawn_wave(wave=self.current_wave, count=ranged_count)

    # ── свойства для HUD/UI ───────────────────────────────────────────────────
    @property
    def wave(self) -> int:
        return self.current_wave

    @property
    def is_between_waves(self) -> bool:
        return self._state == "delay"

    @property
    def time_until_next_wave(self) -> float:
        """Сколько секунд осталось до начала следующей волны."""
        if self._state == "delay":
            return max(0.0, WAVE_START_DELAY - self._timer)
        return 0.0

    @property
    def enemies_remaining(self) -> int:
        return self.slime_mgr.count + self.ranged_mgr.count
