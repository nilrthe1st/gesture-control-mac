"""
Gesture state machine module.

Hierarchy:
    GestureDispatcher
      |-- HoldDetector("Open_Palm"  -> Action.PLAY_PAUSE)
      |-- HoldDetector("Closed_Fist" -> Action.MUTE_TOGGLE)
      |-- SwipeDetector(-> Action.NEXT_TRACK / Action.PREV_TRACK)
      +-- PinchDragDetector(-> Action.VOLUME_UP / Action.VOLUME_DOWN)

All thresholds are read from Config.  No magic numbers inline.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto

from src.actions import Action
from src.config import Config


# ---------------------------------------------------------------------------
# Detection dataclass — the only data the engine ever receives from main.py.
# main.py is responsible for converting raw MediaPipe results to this type.
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    timestamp: float           # time.monotonic() seconds
    gesture_label: str | None  # "Open_Palm", "Closed_Fist", "None", or None (no hand)
    gesture_confidence: float
    wrist_x: float | None      # landmark 0 normalized x
    wrist_y: float | None      # landmark 0 normalized y
    thumb_tip_x: float | None  # landmark 4 normalized x
    thumb_tip_y: float | None  # landmark 4 normalized y
    index_tip_x: float | None  # landmark 8 normalized x
    index_tip_y: float | None  # landmark 8 normalized y


# ---------------------------------------------------------------------------
# HoldDetector
# Transitions:  IDLE -> STABILIZING -> HOLDING -> COOLDOWN -> IDLE
# ---------------------------------------------------------------------------

class _HoldState(Enum):
    IDLE = auto()
    STABILIZING = auto()
    HOLDING = auto()
    COOLDOWN = auto()


class HoldDetector:
    """
    Detects a sustained static gesture and fires one action per hold cycle.

    Hysteresis:
        Enter requires confidence >= config.gesture_confidence_on  (default 0.7)
        Break requires confidence <  config.gesture_confidence_off (default 0.6)
        Values between 0.6 and 0.7 keep the current state.
    """

    def __init__(self, gesture_label: str, action: Action, config: Config) -> None:
        self._label = gesture_label
        self._action = action
        self._config = config
        self._state = _HoldState.IDLE
        self._stable_frames: int = 0
        self._hold_start: float = 0.0
        self._cooldown_start: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, detection: Detection) -> Action | None:
        cfg = self._config

        if self._state is _HoldState.IDLE:
            return self._handle_idle(detection, cfg)
        elif self._state is _HoldState.STABILIZING:
            return self._handle_stabilizing(detection, cfg)
        elif self._state is _HoldState.HOLDING:
            return self._handle_holding(detection, cfg)
        elif self._state is _HoldState.COOLDOWN:
            return self._handle_cooldown(detection, cfg)
        return None  # unreachable, satisfies type checker

    def reset(self) -> None:
        """Return to the initial state unconditionally."""
        self._state = _HoldState.IDLE
        self._stable_frames = 0
        self._hold_start = 0.0
        self._cooldown_start = 0.0

    # ------------------------------------------------------------------
    # Private per-state handlers
    # ------------------------------------------------------------------

    def _gesture_matches(self, detection: Detection) -> bool:
        return detection.gesture_label == self._label

    def _confidence_above_on(self, detection: Detection) -> bool:
        return detection.gesture_confidence >= self._config.gesture_confidence_on

    def _confidence_below_off(self, detection: Detection) -> bool:
        return detection.gesture_confidence < self._config.gesture_confidence_off

    def _gesture_breaks(self, detection: Detection) -> bool:
        """
        A gesture is considered broken when:
          - The label no longer matches, OR
          - The confidence has fallen below the OFF threshold.
        Values between gesture_confidence_off and gesture_confidence_on are
        treated as "uncertain" and do NOT break an in-progress gesture.
        """
        if not self._gesture_matches(detection):
            return True
        if self._confidence_below_off(detection):
            return True
        return False

    def _handle_idle(self, detection: Detection, cfg: Config) -> Action | None:
        if self._gesture_matches(detection) and self._confidence_above_on(detection):
            self._state = _HoldState.STABILIZING
            self._stable_frames = 1  # count the frame that triggered entry
        return None

    def _handle_stabilizing(self, detection: Detection, cfg: Config) -> Action | None:
        if self._gesture_breaks(detection):
            self._state = _HoldState.IDLE
            self._stable_frames = 0
            return None

        # Gesture still valid (confidence may be in the hysteresis band — keep going).
        # stable_frames was set to 1 on entry (in _handle_idle), so we increment first.
        self._stable_frames += 1
        if self._stable_frames >= cfg.hold_stability_frames:
            self._state = _HoldState.HOLDING
            self._hold_start = detection.timestamp
        return None

    def _handle_holding(self, detection: Detection, cfg: Config) -> Action | None:
        if self._gesture_breaks(detection):
            self._state = _HoldState.IDLE
            self._stable_frames = 0
            return None

        elapsed = detection.timestamp - self._hold_start
        if elapsed >= cfg.hold_trigger_seconds:
            self._state = _HoldState.COOLDOWN
            self._cooldown_start = detection.timestamp
            return self._action
        return None

    def _handle_cooldown(self, detection: Detection, cfg: Config) -> Action | None:
        elapsed = detection.timestamp - self._cooldown_start
        if elapsed >= cfg.hold_cooldown_seconds:
            self._state = _HoldState.IDLE
            self._stable_frames = 0
        # All input ignored during cooldown
        return None


# ---------------------------------------------------------------------------
# SwipeDetector — STUB
# Transitions:  TRACKING -> COOLDOWN -> TRACKING
# ---------------------------------------------------------------------------

class _SwipeState(Enum):
    TRACKING = auto()
    COOLDOWN = auto()


class SwipeDetector:
    """
    Detects a horizontal swipe gesture from wrist x-trajectory.

    Structure is complete; actual swipe classification is not yet implemented.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._state = _SwipeState.TRACKING
        self._trajectory: deque[tuple[float, float]] = deque(
            maxlen=config.swipe_window_frames
        )
        self._cooldown_start: float = 0.0

    def update(self, detection: Detection) -> Action | None:
        cfg = self._config

        if self._state is _SwipeState.COOLDOWN:
            elapsed = detection.timestamp - self._cooldown_start
            if elapsed >= cfg.swipe_cooldown_seconds:
                self._state = _SwipeState.TRACKING
                self._trajectory.clear()
            # Nothing to return during cooldown
            return None

        # TRACKING state
        if detection.wrist_x is not None:
            self._trajectory.append((detection.timestamp, detection.wrist_x))

        # TODO: implement swipe detection logic
        return None

    def reset(self) -> None:
        self._state = _SwipeState.TRACKING
        self._trajectory.clear()
        self._cooldown_start = 0.0


# ---------------------------------------------------------------------------
# PinchDragDetector — STUB
# Transitions:  IDLE -> PINCHING -> COOLDOWN_STEP -> PINCHING
# ---------------------------------------------------------------------------

class _PinchState(Enum):
    IDLE = auto()
    PINCHING = auto()
    COOLDOWN_STEP = auto()


class PinchDragDetector:
    """
    Detects pinch (thumb-index distance) and tracks vertical wrist drag to
    control volume.

    Structure is complete; volume step firing is not yet implemented.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._state = _PinchState.IDLE
        self._anchor_y: float | None = None
        self._cooldown_start: float = 0.0

    def update(self, detection: Detection) -> Action | None:
        cfg = self._config

        # Compute thumb-index distance when landmarks are available.
        distance: float | None = None
        if (
            detection.thumb_tip_x is not None
            and detection.thumb_tip_y is not None
            and detection.index_tip_x is not None
            and detection.index_tip_y is not None
        ):
            distance = math.hypot(
                detection.thumb_tip_x - detection.index_tip_x,
                detection.thumb_tip_y - detection.index_tip_y,
            )

        if self._state is _PinchState.IDLE:
            if distance is not None and distance < cfg.pinch_distance_threshold:
                self._state = _PinchState.PINCHING
                self._anchor_y = detection.wrist_y
            return None

        if self._state is _PinchState.PINCHING:
            # Release hysteresis: pinch_release_threshold > pinch_distance_threshold
            if distance is None or distance > cfg.pinch_release_threshold:
                self._state = _PinchState.IDLE
                self._anchor_y = None
                return None

            # TODO: implement volume step logic
            return None

        if self._state is _PinchState.COOLDOWN_STEP:
            elapsed = detection.timestamp - self._cooldown_start
            if elapsed >= cfg.volume_cooldown_seconds:
                self._state = _PinchState.PINCHING
            return None

        return None

    def reset(self) -> None:
        self._state = _PinchState.IDLE
        self._anchor_y = None
        self._cooldown_start = 0.0


# ---------------------------------------------------------------------------
# GestureDispatcher
# Coordinates all sub-detectors.  Priority: hold > swipe > pinch.
# ---------------------------------------------------------------------------

class GestureDispatcher:
    """
    Top-level coordinator.  Feed one Detection per frame; receive at most one
    Action per frame.

    If no hand is detected for >= config.hand_lost_reset_frames consecutive
    frames, every sub-detector is reset to its initial state.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._hold_palm = HoldDetector("Open_Palm", Action.PLAY_PAUSE, config)
        self._hold_fist = HoldDetector("Closed_Fist", Action.MUTE_TOGGLE, config)
        self._swipe = SwipeDetector(config)
        self._pinch = PinchDragDetector(config)
        self._no_hand_frames: int = 0

    def update(self, detection: Detection) -> Action | None:
        # Track consecutive no-hand frames.
        if detection.gesture_label is None:
            self._no_hand_frames += 1
        else:
            self._no_hand_frames = 0

        if self._no_hand_frames >= self._config.hand_lost_reset_frames:
            self.reset_all()
            return None

        # Feed all sub-detectors and return the highest-priority non-None result.
        for detector in (self._hold_palm, self._hold_fist, self._swipe, self._pinch):
            result = detector.update(detection)
            if result is not None:
                return result
        return None

    def reset_all(self) -> None:
        """Reset every sub-detector to its initial state."""
        self._hold_palm.reset()
        self._hold_fist.reset()
        self._swipe.reset()
        self._pinch.reset()
        self._no_hand_frames = 0
