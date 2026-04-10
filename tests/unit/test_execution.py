"""Tests for debugger execution control module (pause, resume, step, speed)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from auto_godot.debugger.errors import DebuggerError
from auto_godot.debugger.execution import (
    get_speed,
    pause_game,
    resume_game,
    set_speed,
    step_frame,
)
from auto_godot.debugger.models import GameState


def _make_session(
    game_paused: bool = False,
    current_speed: float = 1.0,
) -> MagicMock:
    """Create a mock DebugSession with configurable state."""
    session = MagicMock()
    session.game_paused = game_paused
    session.current_speed = current_speed
    session.send_fire_and_forget = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# pause_game
# ---------------------------------------------------------------------------


class TestPauseGame:
    """Tests for pause_game()."""

    @pytest.mark.asyncio()
    async def test_sends_suspend_changed_true(self) -> None:
        """pause_game sends scene:suspend_changed with [True]."""
        session = _make_session()
        await pause_game(session)
        session.send_fire_and_forget.assert_called_once_with(
            "scene:suspend_changed", [True],
        )

    @pytest.mark.asyncio()
    async def test_sets_game_paused_true(self) -> None:
        """pause_game sets session.game_paused = True."""
        session = _make_session(game_paused=False)
        await pause_game(session)
        assert session.game_paused is True

    @pytest.mark.asyncio()
    async def test_returns_game_state_paused(self) -> None:
        """pause_game returns GameState(paused=True)."""
        session = _make_session(current_speed=2.0)
        result = await pause_game(session)
        assert isinstance(result, GameState)
        assert result.paused is True
        assert result.speed == 2.0
        assert result.frame == 0


# ---------------------------------------------------------------------------
# resume_game
# ---------------------------------------------------------------------------


class TestResumeGame:
    """Tests for resume_game()."""

    @pytest.mark.asyncio()
    async def test_sends_suspend_changed_false(self) -> None:
        """resume_game sends scene:suspend_changed with [False]."""
        session = _make_session(game_paused=True)
        await resume_game(session)
        session.send_fire_and_forget.assert_called_once_with(
            "scene:suspend_changed", [False],
        )

    @pytest.mark.asyncio()
    async def test_sets_game_paused_false(self) -> None:
        """resume_game sets session.game_paused = False."""
        session = _make_session(game_paused=True)
        await resume_game(session)
        assert session.game_paused is False

    @pytest.mark.asyncio()
    async def test_returns_game_state_not_paused(self) -> None:
        """resume_game returns GameState(paused=False)."""
        session = _make_session(game_paused=True, current_speed=3.0)
        result = await resume_game(session)
        assert isinstance(result, GameState)
        assert result.paused is False
        assert result.speed == 3.0
        assert result.frame == 0


# ---------------------------------------------------------------------------
# step_frame
# ---------------------------------------------------------------------------


class TestStepFrame:
    """Tests for step_frame()."""

    @pytest.mark.asyncio()
    async def test_auto_pauses_when_running(self) -> None:
        """step_frame sends suspend_changed then next_frame when not paused."""
        session = _make_session(game_paused=False)
        await step_frame(session)
        calls = session.send_fire_and_forget.call_args_list
        assert len(calls) == 2
        assert calls[0].args == ("scene:suspend_changed", [True])
        assert calls[1].args == ("scene:next_frame", [])

    @pytest.mark.asyncio()
    async def test_no_extra_pause_when_already_paused(self) -> None:
        """step_frame sends only next_frame when already paused."""
        session = _make_session(game_paused=True)
        await step_frame(session)
        session.send_fire_and_forget.assert_called_once_with(
            "scene:next_frame", [],
        )

    @pytest.mark.asyncio()
    async def test_returns_game_state_paused(self) -> None:
        """step_frame returns GameState(paused=True) regardless of initial state."""
        session = _make_session(game_paused=False, current_speed=5.0)
        result = await step_frame(session)
        assert isinstance(result, GameState)
        assert result.paused is True
        assert result.speed == 5.0
        assert result.frame == 0

    @pytest.mark.asyncio()
    async def test_sets_game_paused_when_running(self) -> None:
        """step_frame sets session.game_paused = True when it was False."""
        session = _make_session(game_paused=False)
        await step_frame(session)
        assert session.game_paused is True


# ---------------------------------------------------------------------------
# set_speed
# ---------------------------------------------------------------------------


class TestSetSpeed:
    """Tests for set_speed()."""

    @pytest.mark.asyncio()
    async def test_sends_speed_changed(self) -> None:
        """set_speed sends scene:speed_changed with the multiplier."""
        session = _make_session()
        await set_speed(session, 10.0)
        session.send_fire_and_forget.assert_called_once_with(
            "scene:speed_changed", [10.0],
        )

    @pytest.mark.asyncio()
    async def test_sets_current_speed(self) -> None:
        """set_speed updates session.current_speed."""
        session = _make_session()
        await set_speed(session, 10.0)
        assert session.current_speed == 10.0

    @pytest.mark.asyncio()
    async def test_returns_game_state_with_new_speed(self) -> None:
        """set_speed returns GameState with the new speed."""
        session = _make_session(game_paused=True)
        result = await set_speed(session, 10.0)
        assert isinstance(result, GameState)
        assert result.speed == 10.0
        assert result.paused is True
        assert result.frame == 0

    @pytest.mark.asyncio()
    async def test_fractional_speed(self) -> None:
        """set_speed works with fractional multiplier 0.5."""
        session = _make_session()
        result = await set_speed(session, 0.5)
        assert result.speed == 0.5
        session.send_fire_and_forget.assert_called_once_with(
            "scene:speed_changed", [0.5],
        )

    @pytest.mark.asyncio()
    async def test_zero_raises_error(self) -> None:
        """set_speed with 0.0 raises DebuggerError."""
        session = _make_session()
        with pytest.raises(DebuggerError) as exc_info:
            await set_speed(session, 0.0)
        assert exc_info.value.code == "DEBUG_INVALID_SPEED"

    @pytest.mark.asyncio()
    async def test_negative_raises_error(self) -> None:
        """set_speed with negative value raises DebuggerError."""
        session = _make_session()
        with pytest.raises(DebuggerError) as exc_info:
            await set_speed(session, -5.0)
        assert exc_info.value.code == "DEBUG_INVALID_SPEED"

    @pytest.mark.asyncio()
    async def test_no_command_sent_on_invalid_speed(self) -> None:
        """set_speed does not send any command when speed is invalid."""
        session = _make_session()
        with pytest.raises(DebuggerError):
            await set_speed(session, 0.0)
        session.send_fire_and_forget.assert_not_called()


# ---------------------------------------------------------------------------
# get_speed
# ---------------------------------------------------------------------------


class TestGetSpeed:
    """Tests for get_speed()."""

    def test_returns_current_game_state(self) -> None:
        """get_speed returns GameState with current speed, no command sent."""
        session = _make_session(game_paused=True, current_speed=5.0)
        result = get_speed(session)
        assert isinstance(result, GameState)
        assert result.speed == 5.0
        assert result.paused is True
        assert result.frame == 0

    def test_no_command_sent(self) -> None:
        """get_speed does not send any protocol message."""
        session = _make_session()
        get_speed(session)
        session.send_fire_and_forget.assert_not_called()
