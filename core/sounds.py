import numpy as np
import pygame

_RATE = 44100
_initialized = False
_sounds: dict = {}


def _init_mixer():
    global _initialized
    if _initialized:
        return
    pygame.mixer.pre_init(frequency=_RATE, size=-16, channels=1, buffer=512)
    _initialized = True


def pre_init():
    """Call this before pygame.init() to lock in mono mixer settings."""
    _init_mixer()


def _make_sound(samples: np.ndarray) -> pygame.mixer.Sound:
    """Convert a float32 array (values -1..1) into a pygame Sound."""
    data = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    info = pygame.mixer.get_init()
    if info and info[2] == 2:
        data = np.stack([data, data], axis=-1).flatten()
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


def _build_error() -> pygame.mixer.Sound:
    """Harsh buzz — warns participant not to press keys during imagery."""
    dur = 0.40
    t   = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    wave = sum(np.sin(2 * np.pi * 220 * n * t) / n for n in range(1, 6))
    env  = np.exp(-8 * t / dur)
    wave = wave * env * 0.65
    return _make_sound(wave.astype(np.float32))


def _build_milestone_1() -> pygame.mixer.Sound:
    """Tier 1 (Scout): two bright ascending chime notes."""
    dur = 0.65
    t   = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    sp  = int(len(t) * 0.42)
    n1  = np.sin(2*np.pi*1047*t[:sp]) * np.exp(-5*t[:sp]/(dur*0.42)) * 0.50
    t2  = t[sp:] - t[sp]
    n2  = np.sin(2*np.pi*1319*t2)     * np.exp(-5*t2/(dur*0.58))     * 0.55
    return _make_sound(np.concatenate([n1, n2]).astype(np.float32))


def _build_milestone_2() -> pygame.mixer.Sound:
    """Tier 2 (Golden): three-note fanfare with richer harmonics."""
    dur = 0.85
    t   = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    notes = [(784, 0.0, 0.32), (988, 0.28, 0.32), (1175, 0.54, 0.42)]
    wave  = np.zeros(len(t))
    for freq, onset, dec in notes:
        mask = t >= onset
        st = t[mask] - onset
        wave[mask] += sum(np.sin(2*np.pi*freq*n*st)/n for n in range(1, 4)) * np.exp(-4*st/dec) * 0.34
    return _make_sound(np.clip(wave, -1, 1).astype(np.float32))


def _build_milestone_3() -> pygame.mixer.Sound:
    """Tier 3 (Master): four-note triumphant fanfare."""
    dur = 1.10
    t   = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    notes = [(659, 0.0, 0.28), (784, 0.24, 0.28), (988, 0.48, 0.28), (1319, 0.68, 0.48)]
    wave  = np.zeros(len(t))
    for freq, onset, dec in notes:
        mask = t >= onset
        st = t[mask] - onset
        wave[mask] += sum(np.sin(2*np.pi*freq*n*st)/n for n in range(1, 5)) * np.exp(-3*st/dec) * 0.28
    return _make_sound(np.clip(wave, -1, 1).astype(np.float32))


def _build_milestone_4() -> pygame.mixer.Sound:
    """Tier 4 (Emerald): deep gong strike with shimmering high overtone."""
    dur = 1.60
    t   = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    gong = (np.sin(2*np.pi*220*t) * np.exp(-1.8*t) * 0.38 +
            np.sin(2*np.pi*277*t) * np.exp(-2.8*t) * 0.18 +
            np.sin(2*np.pi*440*t) * np.exp(-4.0*t) * 0.12)
    sparkle = np.sin(2*np.pi*2093*t) * np.exp(-8*t) * 0.28
    return _make_sound(np.clip(gong + sparkle, -1, 1).astype(np.float32))


def _build_milestone_5() -> pygame.mixer.Sound:
    """Tier 5 (Diamond): five-note arpeggio + sustained chord swell."""
    dur = 1.90
    t   = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    arp = [(523,0.0,0.38),(659,0.17,0.38),(784,0.34,0.38),(1047,0.51,0.46),(1319,0.67,0.72)]
    wave = np.zeros(len(t))
    for freq, onset, dec in arp:
        mask = t >= onset
        st = t[mask] - onset
        wave[mask] += sum(np.sin(2*np.pi*freq*n*st)/n for n in range(1, 6)) * np.exp(-2.5*st/dec) * 0.27
    swell = np.clip((t - 0.7) / 0.4, 0, 1) * np.exp(-1.2 * np.clip(t - 0.7, 0, None) / 1.2)
    for f in (523, 659, 784, 1047):
        wave += np.sin(2*np.pi*f*t) * swell * 0.07
    return _make_sound(np.clip(wave, -1, 1).astype(np.float32))


def load():
    """Pre-build all sounds. Call once at startup after pygame.init()."""
    _init_mixer()
    _sounds["correct"]     = _build_correct()
    _sounds["incorrect"]   = _build_incorrect()
    _sounds["streak"]      = _build_streak()
    _sounds["error"]       = _build_error()
    _sounds["milestone_1"] = _build_milestone_1()
    _sounds["milestone_2"] = _build_milestone_2()
    _sounds["milestone_3"] = _build_milestone_3()
    _sounds["milestone_4"] = _build_milestone_4()
    _sounds["milestone_5"] = _build_milestone_5()


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
