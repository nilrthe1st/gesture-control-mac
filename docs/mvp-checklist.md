# MVP Implementation Checklist

## Phase 1: Foundation (no camera needed)

- [ ] `src/__init__.py` — empty package marker
- [ ] `src/config.py` — frozen dataclass with all thresholds/cooldowns
- [ ] `tests/__init__.py` — empty package marker
- [ ] `tests/conftest.py` — fast_config fixture, make_detection/make_no_hand factories
- [ ] `tests/test_config.py` — import smoke, replace(), frozen
- [ ] Verify: `pytest tests/test_config.py` passes
- [ ] `src/actions.py` — Action enum + ACTION_TO_COMMAND mapping
- [ ] `tests/test_actions.py` — enum completeness, command map coverage
- [ ] Verify: `pytest tests/test_actions.py` passes

## Phase 2: Gesture Engine (core logic, no camera)

Delegate: vision-engineer

- [ ] `src/gesture_engine.py` — Detection dataclass + HoldDetector
- [ ] `tests/test_gesture_engine.py` — hold tests
- [ ] Verify: `pytest -k hold` passes
- [ ] `src/gesture_engine.py` — add SwipeDetector
- [ ] `tests/test_gesture_engine.py` — add swipe tests
- [ ] Verify: `pytest -k swipe` passes
- [ ] `src/gesture_engine.py` — add PinchDragDetector
- [ ] `tests/test_gesture_engine.py` — add pinch tests
- [ ] Verify: `pytest -k pinch` passes
- [ ] `src/gesture_engine.py` — add GestureDispatcher
- [ ] `tests/test_gesture_engine.py` — add dispatcher tests
- [ ] Verify: `pytest tests/test_gesture_engine.py` passes (all ~18 tests)
- [ ] QA review of gesture_engine.py (qa-reviewer)

## Phase 3: macOS Bridge

Delegate: macos-automation

- [ ] `src/hammerspoon_bridge.py` — dispatch_action + dry_run
- [ ] `tests/test_bridge.py` — mocked subprocess, dry-run, OSError
- [ ] Verify: `pytest tests/test_bridge.py` passes
- [ ] `mac/gesture_control.lua` — hs.urlevent.bind for 6 actions
- [ ] Verify: `open hammerspoon://play_pause` triggers media key

## Phase 4: Integration (needs camera + model)

- [ ] `scripts/download_model.sh` — curl gesture_recognizer.task
- [ ] `models/.gitkeep`
- [ ] Verify: model file exists in models/
- [ ] `src/main.py` — build_recognizer + extract_detection + minimal loop
- [ ] Verify: `python -m src.main --dry-run` shows detections in terminal
- [ ] `src/main.py` — add draw_overlay, finalize loop
- [ ] Verify: landmarks + gesture state visible in OpenCV window
- [ ] QA review of full codebase (qa-reviewer)

## Phase 5: End-to-end verification

- [ ] Palm hold ~1s -> music plays/pauses
- [ ] Swipe right -> next track
- [ ] Swipe left -> previous track
- [ ] Pinch + drag up -> volume increases
- [ ] Pinch + drag down -> volume decreases
- [ ] Fist hold ~1s -> audio mutes
- [ ] Threshold tuning based on manual testing

## Final verification commands

```
pytest tests/                          # all ~26 tests pass
python -m src.main --dry-run           # detections + actions in terminal
open hammerspoon://play_pause          # media toggles from Terminal
python -m src.main                     # full end-to-end
```
