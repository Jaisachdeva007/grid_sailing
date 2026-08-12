import numpy as np
import pygame

_RATE = 44100
_initialized = False
_sounds: dict = {}


def _init_mixer():
    global _initialized
    if _initialized:
        return
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=_RATE, size=-16, channels=1, buffer=512)
    _initialized = True


def _make_sound(samples: np.ndarray) -> pygame.mixer.Sound:
    """Convert a float32 array (values -1..1) into a pygame Sound."""
    data = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    return pygame.mixer.Sound(buffer=data.tobytes())


def _build_correct() -> pygame.mixer.Sound:
    """Warm two-note ascending chime — mouse found the cheese."""
    dur   = 0.45
    t     = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    split = int(len(t) * 0.45)

    # First note: E5 (659 Hz)
    f1  = 659.0
    n1  = np.sin(2 * np.pi * f1 * t[:split])
    env1 = np.exp(-4.5 * t[:split] / (dur * 0.45))

    # Second note: G5 (784 Hz)
    f2   = 784.0
    t2   = t[split:] - t[split]
    n2   = np.sin(2 * np.pi * f2 * t2)
    env2 = np.exp(-4.5 * t2 / (dur * 0.55))

    wave = np.concatenate([n1 * env1 * 0.55, n2 * env2 * 0.55])
    return _make_sound(wave.astype(np.float32))


def _build_incorrect() -> pygame.mixer.Sound:
    """Low dull thud — mouse missed."""
    dur = 0.35
    t   = np.linspace(0, dur, int(_RATE * dur), endpoint=False)

    # Low tone (120 Hz) + slight noise for a thud character
    tone  = np.sin(2 * np.pi * 120 * t)
    noise = np.random.uniform(-0.15, 0.15, len(t))
    env   = np.exp(-9 * t / dur)
    wave  = (tone * 0.5 + noise) * env * 0.55
    return _make_sound(wave.astype(np.float32))


def _build_streak() -> pygame.mixer.Sound:
    """Short bright sparkle for a streak hit (x2+)."""
    dur = 0.25
    t   = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    # Quick rising arpeggio: C6 → E6 → G6
    freqs = [1047, 1319, 1568]
    seg   = len(t) // 3
    wave  = np.zeros(len(t))
    for i, f in enumerate(freqs):
        sl  = slice(i * seg, (i + 1) * seg)
        st  = t[sl] - t[sl][0]
        env = np.exp(-6 * st / (dur / 3))
        wave[sl] = np.sin(2 * np.pi * f * st) * env * 0.45
    return _make_sound(wave.astype(np.float32))


def load():
    """Pre-build all sounds. Call once at startup after pygame.init()."""
    _init_mixer()
    _sounds["correct"]   = _build_correct()
    _sounds["incorrect"] = _build_incorrect()
    _sounds["streak"]    = _build_streak()


def play(name: str):
    """Play a named sound. Safe to call even if load() wasn't called."""
    if not _sounds:
        try:
            load()
        except Exception:
            return
    snd = _sounds.get(name)
    if snd:
        snd.play()
