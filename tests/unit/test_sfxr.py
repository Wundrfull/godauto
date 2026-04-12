"""Tests for sfxr synthesizer and audio generate command."""

from __future__ import annotations

import json
import wave
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli
from auto_godot.sfxr import PRESET_NAMES, SfxrParams, make_preset, synthesize, write_wav


class TestSynthesizeCore:

    def test_default_params_produce_samples(self) -> None:
        samples = synthesize(SfxrParams())
        assert len(samples) > 0
        assert all(-32768 <= s <= 32767 for s in samples)

    def test_seed_deterministic(self) -> None:
        params = SfxrParams(wave_type="noise", base_freq=400.0, decay=0.2)
        assert synthesize(params, seed=42) == synthesize(params, seed=42)

    def test_different_seeds_differ(self) -> None:
        params = SfxrParams(wave_type="noise", base_freq=400.0, decay=0.2)
        assert synthesize(params, seed=1) != synthesize(params, seed=2)

    def test_zero_duration_returns_empty(self) -> None:
        assert synthesize(SfxrParams(attack=0.0, sustain=0.0, decay=0.0)) == []

    def test_all_wave_types(self) -> None:
        for wt in ("square", "sawtooth", "sine", "noise", "triangle"):
            samples = synthesize(SfxrParams(wave_type=wt, sustain=0.05, decay=0.05), seed=1)
            assert len(samples) > 0, f"wave_type={wt} produced no samples"

    def test_frequency_slide_and_arpeggio(self) -> None:
        params = SfxrParams(base_freq=440.0, freq_slide=500.0, arp_speed=0.05, arp_mult=1.5, decay=0.2)
        assert len(synthesize(params, seed=0)) > 0

    def test_freq_limit_stops_early(self) -> None:
        params = SfxrParams(base_freq=200.0, freq_slide=-2000.0, freq_limit=100.0, sustain=0.5, decay=0.5)
        assert len(synthesize(params)) < int(params.sample_rate * params.duration)


class TestWriteWav:

    def test_writes_valid_wav(self, tmp_path: Path) -> None:
        samples = synthesize(SfxrParams(sustain=0.05, decay=0.05))
        out = tmp_path / "test.wav"
        assert write_wav(samples, out) > 0
        with wave.open(str(out), "r") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getnframes() == len(samples)

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "dir" / "sound.wav"
        write_wav(synthesize(SfxrParams(sustain=0.05, decay=0.05)), out)
        assert out.exists()


class TestPresets:

    def test_all_presets_exist(self) -> None:
        expected = {"coin-pickup", "powerup", "explosion", "laser", "jump", "hit", "blip", "success"}
        assert set(PRESET_NAMES) == expected

    def test_each_preset_generates_samples(self) -> None:
        for name in PRESET_NAMES:
            samples = synthesize(make_preset(name, seed=0), seed=0)
            assert len(samples) > 0, f"Preset '{name}' produced no samples"

    def test_presets_deterministic_with_seed(self) -> None:
        for name in PRESET_NAMES:
            s1 = synthesize(make_preset(name, seed=42), seed=42)
            s2 = synthesize(make_preset(name, seed=42), seed=42)
            assert s1 == s2, f"Preset '{name}' not deterministic"


class TestAudioGenerateCommand:

    def test_generate_with_preset(self, tmp_path: Path) -> None:
        out = tmp_path / "coin.wav"
        result = CliRunner().invoke(cli, ["audio", "generate", "--preset", "coin-pickup", str(out)])
        assert result.exit_code == 0, result.output
        assert out.exists()

    def test_generate_with_seed_deterministic(self, tmp_path: Path) -> None:
        out1, out2 = tmp_path / "a.wav", tmp_path / "b.wav"
        runner = CliRunner()
        runner.invoke(cli, ["audio", "generate", "--preset", "laser", "--seed", "42", str(out1)])
        runner.invoke(cli, ["audio", "generate", "--preset", "laser", "--seed", "42", str(out2)])
        assert out1.read_bytes() == out2.read_bytes()

    def test_generate_custom_params(self, tmp_path: Path) -> None:
        out = tmp_path / "custom.wav"
        result = CliRunner().invoke(cli, [
            "audio", "generate", "--wave", "square", "--frequency", "880", "--decay", "0.2", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()

    def test_generate_preset_with_overrides(self, tmp_path: Path) -> None:
        out = tmp_path / "modified.wav"
        result = CliRunner().invoke(cli, [
            "audio", "generate", "--preset", "explosion", "--decay", "1.0", str(out),
        ])
        assert result.exit_code == 0, result.output

    def test_generate_no_params_errors(self) -> None:
        assert CliRunner().invoke(cli, ["audio", "generate", "output.wav"]).exit_code != 0

    def test_generate_json_output(self, tmp_path: Path) -> None:
        out = tmp_path / "coin.wav"
        result = CliRunner().invoke(cli, [
            "-j", "audio", "generate", "--preset", "coin-pickup", "--seed", "7", str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["preset"] == "coin-pickup"
        assert data["seed"] == 7
        assert data["file_size"] > 0

    def test_generate_with_freq_slide(self, tmp_path: Path) -> None:
        out = tmp_path / "slide.wav"
        result = CliRunner().invoke(cli, [
            "audio", "generate", "--wave", "square", "--frequency", "880", "--freq-slide", "-500", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
