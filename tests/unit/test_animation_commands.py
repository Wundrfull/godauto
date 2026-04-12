"""Tests for animation command group."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


class TestCreateLibraryBasic:
    """Verify animation create-library generates valid .tres files."""

    def test_single_animation(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert "AnimationLibrary" in text
        assert 'type="Animation"' in text
        assert "idle" in text

    def test_multiple_animations(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            "--name", "walk",
            "--name", "attack",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "idle" in text
        assert "walk" in text
        assert "attack" in text

    def test_custom_lengths(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle", "--length", "2.0",
            "--name", "attack", "--length", "0.5",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "2" in text  # length = 2
        assert "0.5" in text  # length = 0.5

    def test_loop_mode(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle", "--loop", "linear",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "loop_mode = 1" in text

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "res" / "animations" / "player.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()


class TestCreateLibraryJson:
    """Verify JSON output for create-library."""

    def test_json_output(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "animation", "create-library",
            "--name", "idle",
            "--name", "walk",
            str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["animations"] == ["idle", "walk"]
        assert data["count"] == 2


class TestAddTrack:
    """Verify adding tracks to animations."""

    def _make_library(self, tmp_path: Path) -> Path:
        """Create a library with one animation for testing."""
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle", "--length", "1.0", "--loop", "linear",
            str(out),
        ])
        return out

    def test_add_single_track(self, tmp_path: Path) -> None:
        lib = self._make_library(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", "Sprite2D:modulate:a",
            "--keyframe", "0=1.0",
            "--keyframe", "0.5=0.5",
            "--keyframe", "1.0=1.0",
        ])
        assert result.exit_code == 0, result.output
        text = lib.read_text()
        assert "tracks/0/type" in text
        assert "Sprite2D:modulate:a" in text
        # Godot 4 dict format with separate times/transitions/values arrays
        assert '"times"' in text
        assert '"transitions"' in text
        assert '"values"' in text
        assert '"update"' in text
        assert "PackedFloat32Array" in text

    def test_add_multiple_tracks(self, tmp_path: Path) -> None:
        lib = self._make_library(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", ".:position:x",
            "--keyframe", "0=0",
            "--keyframe", "1.0=10",
        ])
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", ".:position:y",
            "--keyframe", "0=0",
            "--keyframe", "1.0=5",
        ])
        assert result.exit_code == 0
        text = lib.read_text()
        assert "tracks/0/" in text
        assert "tracks/1/" in text

    def test_cubic_interpolation(self, tmp_path: Path) -> None:
        lib = self._make_library(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", ".:scale:x",
            "--keyframe", "0=1",
            "--keyframe", "1.0=2",
            "--interp", "cubic",
        ])
        assert result.exit_code == 0
        text = lib.read_text()
        assert "interp = 2" in text  # cubic = 2

    def test_json_output(self, tmp_path: Path) -> None:
        lib = self._make_library(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", ".:rotation",
            "--keyframe", "0=0",
            "--keyframe", "1.0=3.14",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["animation"] == "idle"
        assert data["track_index"] == 0
        assert data["keyframe_count"] == 2


class TestAddTrackErrors:
    """Verify error handling for add-track."""

    def test_animation_not_found(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(out),
            "--animation", "nonexistent",
            "--property", ".:x",
            "--keyframe", "0=0",
        ])
        assert result.exit_code != 0

    def test_invalid_keyframe_format(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(out),
            "--animation", "idle",
            "--property", ".:x",
            "--keyframe", "invalid",
        ])
        assert result.exit_code != 0

    def test_non_numeric_keyframe(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(out),
            "--animation", "idle",
            "--property", ".:x",
            "--keyframe", "0=abc",
        ])
        assert result.exit_code != 0


class TestListTracks:
    """Verify listing animation tracks."""

    def test_list_empty_library(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        result = runner.invoke(cli, ["animation", "list-tracks", str(out)])
        assert result.exit_code == 0
        assert "idle" in result.output

    def test_list_with_tracks(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle", "--length", "1.0", "--loop", "linear",
            str(out),
        ])
        runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(out),
            "--animation", "idle",
            "--property", "Sprite2D:modulate:a",
            "--keyframe", "0=1", "--keyframe", "1=0",
        ])
        result = runner.invoke(cli, ["animation", "list-tracks", str(out)])
        assert result.exit_code == 0
        assert "idle" in result.output
        assert "1 track" in result.output or "Sprite2D" in result.output

    def test_list_json(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            "--name", "walk",
            str(out),
        ])
        result = runner.invoke(cli, [
            "-j", "animation", "list-tracks", str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2
        assert len(data["animations"]) == 2


def _write_scene_with_player(tmp_path: Path, player_name: str = "AnimPlayer") -> Path:
    """Write a minimal .tscn with an AnimationPlayer child at the root."""
    scene = tmp_path / "test.tscn"
    scene.write_text(
        f'''[gd_scene format=3 uid="uid://abc123"]

[node name="Root" type="Node2D"]

[node name="{player_name}" type="AnimationPlayer" parent="."]
''',
        encoding="utf-8",
    )
    return scene


class TestCreateTree:
    """Verify animation create-tree adds a valid AnimationTree + StateMachine."""

    def test_basic_states_no_transitions(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle,walk,run",
            "--player", "AnimPlayer",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text(encoding="utf-8")
        assert 'type="AnimationNodeAnimation" id="AnimNodeAnimation_idle"' in text
        assert 'type="AnimationNodeAnimation" id="AnimNodeAnimation_walk"' in text
        assert 'type="AnimationNodeAnimation" id="AnimNodeAnimation_run"' in text
        assert 'type="AnimationNodeStateMachine"' in text
        assert '[node name="AnimTree" type="AnimationTree" parent="."]' in text
        assert 'tree_root = SubResource("AnimationNodeStateMachine_root")' in text
        assert 'anim_player = NodePath("../AnimPlayer")' in text
        assert 'callback_mode_discrete = 2' in text
        assert "AnimationNodeStateMachineTransition" not in text

    def test_blend_times_generate_transitions(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle,walk",
            "--player", "AnimPlayer",
            "--blend-times", "idle->walk:0.15,walk->idle:0.2",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text(encoding="utf-8")
        assert 'AnimNodeStateMachineTransition_idle_walk' in text
        assert 'AnimNodeStateMachineTransition_walk_idle' in text
        assert 'xfade_time = 0.15' in text
        assert 'xfade_time = 0.2' in text
        assert '"idle", "walk", SubResource(' in text
        assert '"walk", "idle", SubResource(' in text

    def test_any_wildcard_expands_to_every_other_state(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle,walk,jump",
            "--player", "AnimPlayer",
            "--blend-times", "any->jump:0.05",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text(encoding="utf-8")
        assert 'AnimNodeStateMachineTransition_idle_jump' in text
        assert 'AnimNodeStateMachineTransition_walk_jump' in text
        assert 'AnimNodeStateMachineTransition_jump_jump' not in text

    def test_state_positions_spaced_for_editor(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "a,b",
            "--player", "AnimPlayer",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text(encoding="utf-8")
        assert 'states/a/position = Vector2(200, 100)' in text
        assert 'states/b/position = Vector2(400, 100)' in text

    def test_missing_player_errors(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle,walk",
            "--player", "MissingPlayer",
        ])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_wrong_player_type_errors(self, tmp_path: Path) -> None:
        scene = tmp_path / "test.tscn"
        scene.write_text(
            '''[gd_scene format=3 uid="uid://abc"]

[node name="Root" type="Node2D"]

[node name="AnimPlayer" type="Timer" parent="."]
''',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle",
            "--player", "AnimPlayer",
        ])
        assert result.exit_code != 0
        assert "AnimationPlayer" in result.output

    def test_duplicate_tree_name_errors(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        first = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle",
            "--player", "AnimPlayer",
        ])
        assert first.exit_code == 0
        second = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "walk",
            "--player", "AnimPlayer",
        ])
        assert second.exit_code != 0
        assert "already exists" in second.output.lower()

    def test_duplicate_state_name_errors(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle,walk,idle",
            "--player", "AnimPlayer",
        ])
        assert result.exit_code != 0
        assert "duplicate" in result.output.lower()

    def test_invalid_blend_time_format_errors(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle,walk",
            "--player", "AnimPlayer",
            "--blend-times", "idle=walk:0.1",
        ])
        assert result.exit_code != 0
        assert "blend-time" in result.output.lower()

    def test_blend_time_to_unknown_state_errors(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle,walk",
            "--player", "AnimPlayer",
            "--blend-times", "idle->fly:0.1",
        ])
        assert result.exit_code != 0
        assert "fly" in result.output

    def test_player_not_at_root_errors(self, tmp_path: Path) -> None:
        scene = tmp_path / "test.tscn"
        scene.write_text(
            '''[gd_scene format=3 uid="uid://abc"]

[node name="Root" type="Node2D"]

[node name="Child" type="Node2D" parent="."]

[node name="AnimPlayer" type="AnimationPlayer" parent="Child"]
''',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle",
            "--player", "AnimPlayer",
        ])
        assert result.exit_code != 0
        assert "root" in result.output.lower()

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle,walk",
            "--player", "AnimPlayer",
            "--blend-times", "idle->walk:0.1",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output[result.output.index("{"):])
        assert data["created"] is True
        assert data["state_count"] == 2
        assert data["transition_count"] == 1
        assert data["states"] == ["idle", "walk"]
        assert data["player"] == "AnimPlayer"

    def test_round_trip_parseable(self, tmp_path: Path) -> None:
        """Generated .tscn must re-parse cleanly."""
        from auto_godot.formats.tscn import parse_tscn
        scene = _write_scene_with_player(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-tree",
            "--scene", str(scene),
            "--name", "AnimTree",
            "--states", "idle,walk,run",
            "--player", "AnimPlayer",
            "--blend-times", "idle->walk:0.15,any->run:0.1",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text(encoding="utf-8")
        reparsed = parse_tscn(text)
        tree_nodes = [n for n in reparsed.nodes if n.type == "AnimationTree"]
        assert len(tree_nodes) == 1
        assert tree_nodes[0].name == "AnimTree"
        sm_subs = [s for s in reparsed.sub_resources if s.type == "AnimationNodeStateMachine"]
        assert len(sm_subs) == 1
        trans_subs = [s for s in reparsed.sub_resources if s.type == "AnimationNodeStateMachineTransition"]
        assert len(trans_subs) == 3
