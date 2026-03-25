# Gesture Control Mac

Goal: build a local macOS hand-gesture controller using webcam input.

Stack:
- Python 3.11
- MediaPipe Gesture Recognizer and/or Hand Landmarker
- OpenCV for camera preview + overlay
- Hammerspoon for macOS media/system control

MVP gestures:
- open palm hold -> play/pause
- swipe right -> next track
- swipe left -> previous track
- pinch + move up/down -> volume up/down
- fist hold -> mute

Constraints:
- local only, no cloud backend
- keep logic modular and testable
- prefer deterministic gesture state machines over magical heuristics
- separate static gesture detection from dynamic motion detection
- centralize thresholds/cooldowns in config
- do not claim completion without running the narrowest meaningful verification

Repo conventions:
- src/config.py for thresholds and settings
- src/actions.py for action enums + command mapping
- src/hammerspoon_bridge.py for macOS bridge
- src/gesture_engine.py for gesture state machine logic
- src/main.py for the webcam loop
- mac/gesture_control.lua for Hammerspoon
- tests/ for pure logic tests

Subagent routing:
- use vision-engineer for MediaPipe, camera loop, smoothing, thresholds, overlays
- use macos-automation for Hammerspoon, hs CLI bridge, permissions notes
- use qa-reviewer after every significant code change
