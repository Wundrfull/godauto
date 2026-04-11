"""Execution control for a connected Godot game.

Provides async functions that send fire-and-forget debugger protocol
commands to pause, resume, step, and adjust game speed. Each function
updates local session state proactively (rather than waiting for the
recv loop to process confirmation messages) to avoid race conditions.

All functions return a GameState snapshot suitable for --json output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from auto_godot.debugger.errors import DebuggerError
from auto_godot.debugger.models import GameState

if TYPE_CHECKING:
    from auto_godot.debugger.session import DebugSession


async def pause_game(session: DebugSession) -> GameState:
    """Pause the running game.

    Sends scene:suspend_changed with True. The game confirms by
    sending a debug_enter message (handled by the recv loop).
    """
    await session.send_fire_and_forget("scene:suspend_changed", [True])
    session.game_paused = True
    return GameState(paused=True, speed=session.current_speed, frame=0)


async def resume_game(session: DebugSession) -> GameState:
    """Resume a paused game.

    Sends scene:suspend_changed with False. The game confirms by
    sending a debug_exit message (handled by the recv loop).
    """
    await session.send_fire_and_forget("scene:suspend_changed", [False])
    session.game_paused = False
    return GameState(paused=False, speed=session.current_speed, frame=0)


async def step_frame(session: DebugSession) -> GameState:
    """Advance one frame while paused.

    If the game is currently running, it is paused first (D-10
    discretion: auto-pause if running). Then sends scene:next_frame
    to advance exactly one physics/process frame. The game remains
    paused after stepping.
    """
    if not session.game_paused:
        await session.send_fire_and_forget("scene:suspend_changed", [True])
        session.game_paused = True
    await session.send_fire_and_forget("scene:next_frame", [])
    return GameState(paused=True, speed=session.current_speed, frame=0)


async def set_speed(session: DebugSession, multiplier: float) -> GameState:
    """Set the game speed multiplier.

    Validates that multiplier is positive, then sends
    scene:speed_changed. Updates session.current_speed immediately.
    """
    if multiplier <= 0.0:
        raise DebuggerError(
            message=f"Speed multiplier must be positive, got {multiplier}",
            code="DEBUG_INVALID_SPEED",
            fix="Use a positive number (e.g., debug speed 10)",
        )
    await session.send_fire_and_forget("scene:speed_changed", [multiplier])
    session.current_speed = multiplier
    return GameState(paused=session.game_paused, speed=multiplier, frame=0)


def get_speed(session: DebugSession) -> GameState:
    """Query the current game speed without sending any command.

    Returns a GameState snapshot from local session state.
    """
    return GameState(
        paused=session.game_paused,
        speed=session.current_speed,
        frame=0,
    )
