---
name: project_context
description: Core architecture and reviewer patterns for gesture-control-mac
type: project
---

gesture-control-mac: local macOS hand-gesture controller using webcam, MediaPipe, OpenCV, Hammerspoon.

Stack: Python 3.11, but code must remain compatible with 3.9+ (use `from __future__ import annotations` for union type hints).

Key files: src/config.py (Config dataclass, frozen), src/gesture_engine.py (HoldDetector, SwipeDetector, PinchDragDetector, GestureDispatcher), src/main.py (webcam loop + draw_overlay), tests/conftest.py (fast_config fixture, make_detection, make_no_hand helpers).

FSM states for HoldDetector: IDLE -> STABILIZING -> HOLDING -> COOLDOWN -> IDLE.
- _hold_start is set to detection.timestamp when entering HOLDING (in _handle_stabilizing).
- hold_start property returns _hold_start only when state is HOLDING or COOLDOWN.
- Both palm and fist detectors cannot be non-IDLE simultaneously in practice (each breaks on label mismatch).

fast_config fixture: hold_stability_frames=2, hold_trigger_seconds=0.0, hold_cooldown_seconds=0.0.

**Why:** Helps future reviews quickly orient to the codebase without reading every file.
**How to apply:** Use when reviewing new PRs to check consistency with established FSM patterns and config conventions.
