"""Pure Python sfxr-style retro sound synthesizer."""

from __future__ import annotations

import math
import random
import struct
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SfxrParams:
    """Parameters controlling sfxr sound generation."""

    wave_type: str = "square"
    sample_rate: int = 22050
    base_freq: float = 440.0
    freq_limit: float = 0.0
    freq_slide: float = 0.0
    duty_cycle: float = 0.5
    attack: float = 0.0
    sustain: float = 0.1
    decay: float = 0.3
    volume: float = 0.8
    arp_speed: float = 0.0
    arp_mult: float = 1.0

    @property
    def duration(self) -> float:
        return self.attack + self.sustain + self.decay


def synthesize(params: SfxrParams, seed: int | None = None) -> list[int]:
    """Generate 16-bit signed audio samples from sfxr parameters."""
    rng = random.Random(seed)
    sr = params.sample_rate
    num_samples = int(sr * params.duration)
    if num_samples == 0:
        return []

    samples: list[int] = []
    phase = 0.0
    freq = params.base_freq
    arp_triggered = False
    noise_buffer = [rng.uniform(-1.0, 1.0) for _ in range(32)]

    for i in range(num_samples):
        t = i / sr
        amp = _envelope(t, params.attack, params.sustain, params.decay)

        freq += params.freq_slide / sr
        if params.freq_limit > 0.0 and freq < params.freq_limit:
            break

        if params.arp_speed > 0.0 and t >= params.arp_speed and not arp_triggered:
            freq *= params.arp_mult
            arp_triggered = True

        effective_freq = max(1.0, freq)
        phase += effective_freq / sr
        phase %= 1.0

        val = _waveform(params.wave_type, phase, params.duty_cycle, noise_buffer)
        sample = int(val * amp * params.volume * 32767)
        samples.append(max(-32768, min(32767, sample)))

    return samples


def write_wav(samples: list[int], path: Path, sample_rate: int = 22050) -> int:
    """Write samples to a WAV file. Returns file size in bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return path.stat().st_size


def _envelope(t: float, attack: float, sustain: float, decay: float) -> float:
    if attack > 0.0 and t < attack:
        return t / attack
    t -= attack
    if t < sustain:
        return 1.0
    t -= sustain
    if decay > 0.0 and t < decay:
        return 1.0 - (t / decay)
    return 0.0


def _waveform(
    wave_type: str, phase: float, duty: float, noise_buf: list[float]
) -> float:
    if wave_type == "square":
        return 1.0 if phase < duty else -1.0
    if wave_type == "sawtooth":
        return 2.0 * phase - 1.0
    if wave_type == "sine":
        return math.sin(2.0 * math.pi * phase)
    if wave_type == "triangle":
        return 4.0 * abs(phase - 0.5) - 1.0
    if wave_type == "noise":
        return noise_buf[int(phase * len(noise_buf)) % len(noise_buf)]
    return 0.0


# Preset definitions: {param: (base, spread)} for randomized values,
# plain values for wave_type and volume.
_PRESET_DEFS: dict[str, dict[str, tuple[float, float] | str | float]] = {
    "coin-pickup": {
        "wave_type": "square", "volume": 0.7, "duty_cycle": (0.5, 0.0),
        "base_freq": (600.0, 50.0), "sustain": (0.04, 0.01),
        "decay": (0.15, 0.03), "arp_speed": (0.04, 0.01), "arp_mult": (1.5, 0.1),
    },
    "powerup": {
        "wave_type": "square", "volume": 0.7, "duty_cycle": (0.5, 0.0),
        "base_freq": (300.0, 30.0), "freq_slide": (800.0, 100.0),
        "sustain": (0.15, 0.03), "decay": (0.3, 0.05),
    },
    "explosion": {
        "wave_type": "noise", "volume": 0.8,
        "base_freq": (150.0, 30.0), "freq_slide": (-50.0, 20.0),
        "sustain": (0.05, 0.02), "decay": (0.5, 0.1),
    },
    "laser": {
        "wave_type": "square", "volume": 0.7, "duty_cycle": (0.3, 0.0),
        "base_freq": (900.0, 100.0), "freq_slide": (-600.0, 80.0),
        "sustain": (0.05, 0.01), "decay": (0.15, 0.03),
    },
    "jump": {
        "wave_type": "sine", "volume": 0.7,
        "base_freq": (300.0, 30.0), "freq_slide": (500.0, 60.0),
        "sustain": (0.05, 0.01), "decay": (0.2, 0.03),
    },
    "hit": {
        "wave_type": "noise", "volume": 0.8,
        "base_freq": (400.0, 50.0), "freq_slide": (-100.0, 30.0),
        "sustain": (0.02, 0.005), "decay": (0.15, 0.03),
    },
    "blip": {
        "wave_type": "sine", "volume": 0.6,
        "base_freq": (800.0, 60.0), "sustain": (0.03, 0.005),
        "decay": (0.08, 0.02),
    },
    "success": {
        "wave_type": "square", "volume": 0.7, "duty_cycle": (0.5, 0.0),
        "base_freq": (500.0, 30.0), "arp_speed": (0.08, 0.01),
        "arp_mult": (1.25, 0.05), "sustain": (0.1, 0.02), "decay": (0.35, 0.05),
    },
}

PRESET_NAMES: list[str] = list(_PRESET_DEFS.keys())


def make_preset(name: str, seed: int | None = None) -> SfxrParams:
    """Build SfxrParams for a named preset with optional seed variation."""
    defn = _PRESET_DEFS[name]
    rng = random.Random(seed)
    kwargs: dict[str, object] = {}
    for key, val in defn.items():
        if isinstance(val, tuple):
            base, spread = val
            kwargs[key] = base + rng.uniform(-spread, spread)
        else:
            kwargs[key] = val
    return SfxrParams(**kwargs)  # type: ignore[arg-type]
