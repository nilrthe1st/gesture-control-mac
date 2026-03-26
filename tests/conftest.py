from __future__ import annotations

import time
import pytest
from src.config import Config
from src.gesture_engine import Detection


@pytest.fixture
def fast_config() -> Config:
    """Config with zero-delay timers for fast unit tests."""
    return Config(
        hold_stability_frames=2,
        hold_trigger_seconds=0.0,
        hold_cooldown_seconds=0.0,
        swipe_cooldown_seconds=0.0,
        volume_cooldown_seconds=0.0,
    )


def make_detection(
    gesture_label: str | None = "Open_Palm",
    gesture_confidence: float = 0.9,
    wrist_x: float | None = 0.5,
    wrist_y: float | None = 0.5,
    thumb_tip_x: float | None = 0.45,
    thumb_tip_y: float | None = 0.45,
    index_tip_x: float | None = 0.5,
    index_tip_y: float | None = 0.35,
    timestamp: float | None = None,
) -> Detection:
    return Detection(
        timestamp=timestamp if timestamp is not None else time.monotonic(),
        gesture_label=gesture_label,
        gesture_confidence=gesture_confidence,
        wrist_x=wrist_x,
        wrist_y=wrist_y,
        thumb_tip_x=thumb_tip_x,
        thumb_tip_y=thumb_tip_y,
        index_tip_x=index_tip_x,
        index_tip_y=index_tip_y,
    )


def make_no_hand(timestamp: float | None = None) -> Detection:
    return Detection(
        timestamp=timestamp if timestamp is not None else time.monotonic(),
        gesture_label=None,
        gesture_confidence=0.0,
        wrist_x=None,
        wrist_y=None,
        thumb_tip_x=None,
        thumb_tip_y=None,
        index_tip_x=None,
        index_tip_y=None,
    )
