# MVP Architecture: Gesture Control Mac

## Context

Local macOS webcam hand gesture controller. Hand gestures control media playback (play/pause, next/prev track, volume, mute) via:

```
Webcam → MediaPipe GestureRecognizer → Python state machine → Hammerspoon URL scheme → macOS
```

---

## Key Design Decisions

1. **MediaPipe VIDEO mode (sync), not LIVE_STREAM (async)** — VIDEO mode processes every frame deterministically via `recognize_for_video()`. LIVE_STREAM silently drops frames when processing is slow, which corrupts swipe trajectory data. At 640x480 on Apple Silicon, inference is ~15ms — well within 30fps budget. No callbacks, no threading, no race conditions.

2. **GestureRecognizer alone (not HandLandmarker)** — GestureRecognizer provides both gesture labels (Open_Palm, Closed_Fist) AND 21 hand landmarks in a single inference. No need for two pipelines.

3. **Horizontal mirror before processing** — `cv2.flip(frame, 1)` before MediaPipe so landmarks are already in mirrored space. Swipe right = user moves hand right.

4. **Frozen dataclass for config** — Type-safe, IDE autocomplete, testable via `replace()`.

5. **Detection dataclass as testability boundary** — The gesture engine never touches MediaPipe objects. `main.py` extracts a `Detection` dataclass from MediaPipe results; the engine is a pure function of `(state, Detection) -> (state, Optional[Action])`.

6. **Per-gesture cooldowns (not global)** — Allows quick gesture switching (e.g., swipe then immediately pinch).

---

## File Tree

```
src/
  __init__.py              # empty package marker
  config.py                # frozen dataclass with ALL thresholds/cooldowns
  actions.py               # Action enum + ACTION_TO_COMMAND mapping
  hammerspoon_bridge.py    # dispatch_action() via subprocess open -g hammerspoon://
  gesture_engine.py        # Detection, HoldDetector, SwipeDetector, PinchDragDetector, GestureDispatcher
  main.py                  # webcam loop, MediaPipe VIDEO mode, overlay, integration
mac/
  gesture_control.lua      # hs.urlevent.bind() for 6 actions
tests/
  __init__.py
  conftest.py              # fast_config fixture, make_detection/make_no_hand factories
  test_config.py           # import smoke, replace(), frozen
  test_actions.py          # enum coverage, command map completeness
  test_gesture_engine.py   # ~18 tests: holds, swipes, pinch, dispatcher, edge cases
  test_bridge.py           # mocked subprocess, dry-run, error handling
scripts/
  download_model.sh        # curl gesture_recognizer.task to models/
models/
  .gitkeep
```

---

## Gesture State Machine Design

### Architecture: Gesture-specific sub-FSMs coordinated by a top-level dispatcher

```
GestureDispatcher
  |-- HoldDetector("Open_Palm" -> PLAY_PAUSE)
  |-- HoldDetector("Closed_Fist" -> MUTE_TOGGLE)
  |-- SwipeDetector(-> NEXT_TRACK / PREV_TRACK)
  +-- PinchDragDetector(-> VOLUME_UP / VOLUME_DOWN)
```

Each frame: dispatcher feeds Detection to ALL sub-FSMs, collects actions, returns first non-null (priority: hold > swipe > pinch). If no hand for >= 2 frames, all sub-FSMs reset.

### Detection dataclass (engine input)

```
Detection:
  timestamp: float          # time.monotonic() seconds
  gesture_label: str | None # "Open_Palm", "Closed_Fist", "None", or None (no hand)
  gesture_confidence: float
  wrist_x/y: float | None  # landmark 0
  thumb_tip_x/y: float | None  # landmark 4
  index_tip_x/y: float | None  # landmark 8
```

### HoldDetector (palm -> play/pause, fist -> mute)

```
States: IDLE -> STABILIZING -> HOLDING -> COOLDOWN

IDLE:        gesture matches with confidence >= 0.7 -> STABILIZING
STABILIZING: 4 consecutive frames stable -> HOLDING (record start time)
             gesture breaks -> IDLE
HOLDING:     elapsed >= 0.8s -> fire action -> COOLDOWN
             gesture breaks -> IDLE
COOLDOWN:    elapsed >= 1.2s -> IDLE (ignore all input during cooldown)
```

Hysteresis: on at 0.7, off at 0.6 (prevents flickering at threshold).

### SwipeDetector (swipe right -> next, swipe left -> prev)

```
States: TRACKING -> COOLDOWN

TRACKING: maintain deque of (timestamp, wrist_x, wrist_y), max 14 entries
  When full:
    delta_x = newest.x - oldest.x
    delta_y = abs(newest.y - oldest.y)
    if delta_x > 0.18 and delta_y < 0.10 -> fire NEXT_TRACK -> COOLDOWN, clear deque
    if delta_x < -0.18 and delta_y < 0.10 -> fire PREV_TRACK -> COOLDOWN, clear deque
COOLDOWN: 0.5s then resume TRACKING
```

Delta_y check rejects diagonal motion. Threshold 0.18 (~115px at 640w) avoids drift triggers during holds.

### PinchDragDetector (pinch + vertical drag -> volume)

```
States: IDLE -> PINCHING -> COOLDOWN_STEP

IDLE:          thumb-index distance < 0.05 -> PINCHING, record anchor_y = wrist_y
PINCHING:      distance > 0.08 (hysteresis) -> IDLE
               delta_y = anchor_y - wrist_y (up = y decreases in image coords)
               |delta_y| >= 0.03 -> fire VOLUME_UP or VOLUME_DOWN
                 -> update anchor_y to current (incremental stepping)
                 -> COOLDOWN_STEP
COOLDOWN_STEP: 0.3s then back to PINCHING (not IDLE -- stay in pinch mode)
```

Pinch detection ignores gesture_label entirely -- works purely from landmark distances.

---

## Static vs Dynamic Gesture Split

| Gesture | Type | Detection Method |
|---------|------|-----------------|
| Open palm hold -> play/pause | **Static** | MediaPipe `gesture_label == "Open_Palm"` + hold timer |
| Fist hold -> mute | **Static** | MediaPipe `gesture_label == "Closed_Fist"` + hold timer |
| Swipe right -> next track | **Dynamic** | Wrist x-trajectory over sliding window |
| Swipe left -> prev track | **Dynamic** | Wrist x-trajectory over sliding window |
| Pinch + drag up -> volume up | **Compound** | Thumb-index distance + wrist y-delta |
| Pinch + drag down -> volume down | **Compound** | Thumb-index distance + wrist y-delta |

---

## Thresholds & Cooldowns (all in config.py)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| gesture_confidence_on | 0.7 | Reliable recognition threshold |
| gesture_confidence_off | 0.6 | Hysteresis band |
| hold_stability_frames | 4 | ~133ms at 30fps, filters flicker |
| hold_trigger_seconds | 0.8 | Responsive but intentional |
| hold_cooldown_seconds | 1.2 | Prevents double-trigger |
| swipe_window_frames | 14 | ~467ms window |
| swipe_min_delta_x | 0.18 | Deliberate motion only |
| swipe_max_delta_y | 0.10 | Reject diagonal |
| swipe_cooldown_seconds | 0.5 | Allow quick consecutive swipes |
| pinch_distance_threshold | 0.05 | Normalized thumb-index distance |
| pinch_release_threshold | 0.08 | Hysteresis for stable pinch |
| volume_step_delta_y | 0.03 | ~19px at 480h per step |
| volume_cooldown_seconds | 0.3 | Smooth stepping |
| hand_lost_reset_frames | 2 | Quick reset on hand loss |

---

## Hammerspoon Bridge

**Python side** (`src/hammerspoon_bridge.py`):
```python
subprocess.Popen(["open", "-g", f"hammerspoon://{command}"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```
`-g` flag = background, no focus change. Plus `dispatch_action_dry_run()` for `--dry-run` mode.

**Lua side** (`mac/gesture_control.lua`):
- Media keys via `hs.eventtap.event.newSystemKeyEvent("PLAY"|"NEXT"|"PREVIOUS", true/false):post()`
- Volume via `hs.audiodevice.defaultOutputDevice():setVolume(current +/- 5)`
- Mute via `hs.audiodevice.defaultOutputDevice():setMuted(not muted)`
- `hs.alert.show()` for brief visual confirmation

---

## Testing Plan

All tests run without a camera. The gesture engine consumes `Detection` dataclasses, not MediaPipe objects.

**test_config.py** (3 tests): import smoke, replace override, frozen immutability
**test_actions.py** (2 tests): enum completeness, command map coverage
**test_gesture_engine.py** (~18 tests):
- Hold: triggers correctly, resets on break, cooldown blocks retrigger, confidence threshold, hysteresis
- Swipe: right->next, left->prev, diagonal rejected, cooldown, small motion ignored
- Pinch: up->vol_up, down->vol_down, release resets, incremental multi-step
- Dispatcher: hand loss resets all, one action per frame priority
**test_bridge.py** (3 tests): subprocess mock, dry-run URL, OSError handling

Fixtures in `conftest.py`: `fast_config` (zero-delay timers), `make_detection()` / `make_no_hand()` factories.
