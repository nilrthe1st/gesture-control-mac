# gesture-control-mac

Local macOS hand-gesture controller using webcam input. Control media playback with hand gestures — no cloud backend.

```
Webcam → MediaPipe GestureRecognizer → Python state machine → Hammerspoon URL scheme → macOS
```

## Gestures

| Gesture | Action |
|---------|--------|
| Open palm hold (~0.8s) | Play / Pause |
| Swipe right | Next track |
| Swipe left | Previous track |
| Pinch + drag up | Volume up |
| Pinch + drag down | Volume down |
| Fist hold (~0.8s) | Mute toggle |

## Requirements

- macOS (Apple Silicon or Intel)
- Python 3.11+
- [Hammerspoon](https://www.hammerspoon.org/) installed and running
- Webcam

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Download the MediaPipe gesture model

```bash
bash scripts/download_model.sh
```

This places `gesture_recognizer.task` in `models/`.

### 3. Install the Hammerspoon config

Copy or symlink the Lua config into Hammerspoon's config directory:

```bash
mkdir -p ~/.hammerspoon
cp mac/gesture_control.lua ~/.hammerspoon/gesture_control.lua
```

Then add this line to `~/.hammerspoon/init.lua`:

```lua
require("gesture_control")
```

Reload Hammerspoon: click the menubar icon → **Reload Config**.

### 4. Grant permissions

Hammerspoon needs **Accessibility** permission to send media keys:
- System Settings → Privacy & Security → Accessibility → enable Hammerspoon

### 5. Test the Hammerspoon bridge

```bash
open hammerspoon://play_pause
```

You should see a brief alert and hear media toggle.

## Running

### Dry-run mode (no real actions fired)

```bash
python -m src.main --dry-run
```

Prints detected gestures and triggered actions to the terminal. No macOS commands are sent.

### Normal mode

```bash
python -m src.main
```

Press **q** in the preview window to quit.

## Tests

```bash
pytest tests/
```

All tests run without a camera or model file.

## Project layout

```
src/
  config.py              # All thresholds and settings (frozen dataclass)
  actions.py             # Action enum + ACTION_TO_COMMAND mapping
  hammerspoon_bridge.py  # dispatch_action() via open -g hammerspoon://
  gesture_engine.py      # Detection dataclass + gesture state machines
  main.py                # Webcam loop, MediaPipe VIDEO mode, overlay
mac/
  gesture_control.lua    # Hammerspoon hs.urlevent handlers
models/                  # gesture_recognizer.task (downloaded, not committed)
tests/                   # Pure logic tests, no camera needed
scripts/
  download_model.sh      # Fetches the MediaPipe model
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for design decisions and state machine diagrams.
