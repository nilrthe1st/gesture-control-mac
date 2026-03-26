"""
Webcam loop for gesture-control-mac.

Usage:
    python -m src.main [--camera INDEX] [--model PATH] [--dry-run]

Flags:
    --camera   Camera device index (default: from DEFAULT_CONFIG)
    --model    Path to the MediaPipe gesture_recognizer.task file
               (default: from DEFAULT_CONFIG)
    --dry-run  Print detected gestures and actions to stdout instead of
               dispatching Hammerspoon commands.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import GestureRecognizerResult

from src.actions import Action
from src.config import DEFAULT_CONFIG, Config
from src.gesture_engine import Detection, GestureDispatcher
from src.hammerspoon_bridge import dispatch_action, dispatch_action_dry_run


# ---------------------------------------------------------------------------
# MediaPipe setup
# ---------------------------------------------------------------------------

def build_recognizer(config: Config) -> mp_vision.GestureRecognizer:
    """Create a MediaPipe GestureRecognizer in VIDEO (synchronous) mode."""
    base_options = mp_python.BaseOptions(model_asset_path=config.model_path)
    options = mp_vision.GestureRecognizerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_hands=1,
    )
    return mp_vision.GestureRecognizer.create_from_options(options)


# ---------------------------------------------------------------------------
# Result extraction
# ---------------------------------------------------------------------------

def extract_detection(result: GestureRecognizerResult, timestamp: float) -> Detection:
    """
    Convert a MediaPipe GestureRecognizerResult to a Detection dataclass.

    If no hand is present all landmark fields are None and gesture_label is None.
    """
    if not result.hand_landmarks:
        return Detection(
            timestamp=timestamp,
            gesture_label=None,
            gesture_confidence=0.0,
            wrist_x=None,
            wrist_y=None,
            thumb_tip_x=None,
            thumb_tip_y=None,
            index_tip_x=None,
            index_tip_y=None,
        )

    landmarks = result.hand_landmarks[0]

    # Landmark indices: 0 = wrist, 4 = thumb tip, 8 = index tip
    wrist = landmarks[0]
    thumb_tip = landmarks[4]
    index_tip = landmarks[8]

    if result.gestures:
        top_gesture = result.gestures[0][0]
        gesture_label: str | None = top_gesture.category_name
        gesture_confidence: float = top_gesture.score
    else:
        gesture_label = "None"
        gesture_confidence = 0.0

    return Detection(
        timestamp=timestamp,
        gesture_label=gesture_label,
        gesture_confidence=gesture_confidence,
        wrist_x=wrist.x,
        wrist_y=wrist.y,
        thumb_tip_x=thumb_tip.x,
        thumb_tip_y=thumb_tip.y,
        index_tip_x=index_tip.x,
        index_tip_y=index_tip.y,
    )


# ---------------------------------------------------------------------------
# Overlay drawing
# ---------------------------------------------------------------------------

def draw_overlay(
    frame: cv2.Mat,
    detection: Detection,
    action: Action | None,
    fps: float,
    hold_states: dict | None = None,
    config: Config | None = None,
) -> None:
    """Draw gesture label, action, FPS counter, and hold phase onto frame in-place."""
    h, w = frame.shape[:2]

    label_text = (
        f"{detection.gesture_label} ({detection.gesture_confidence:.2f})"
        if detection.gesture_label is not None
        else "No hand"
    )
    action_text = action.name if action is not None else "\u2014"  # em dash

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.65
    thickness = 2
    color_white = (255, 255, 255)
    color_green = (0, 220, 80)
    color_yellow = (0, 210, 255)
    color_orange = (0, 165, 255)   # BGR: orange
    color_grey = (140, 140, 140)
    bg_color = (30, 30, 30)
    padding = 6

    lines = [
        (f"Gesture: {label_text}", color_white),
        (f"Action:  {action_text}", color_green),
        (f"FPS:     {fps:.1f}", color_yellow),
    ]

    # Determine hold phase line and progress bar parameters from hold_states.
    hold_phase_text: str | None = None
    hold_phase_color = color_white
    hold_progress: float | None = None  # 0.0–1.0 when HOLDING, else None

    if hold_states is not None:
        # Prefer whichever detector is in a non-IDLE state (palm checked first).
        active_state: str | None = None
        active_hold_start: float = 0.0
        for key in ("palm", "fist"):
            entry = hold_states[key]
            if entry["state"] != "IDLE":
                active_state = entry["state"]
                active_hold_start = entry["hold_start"]
                break

        if active_state == "STABILIZING":
            hold_phase_text = "Hold: STABILIZING"
            hold_phase_color = color_yellow
        elif active_state == "HOLDING":
            if config is not None:
                elapsed = detection.timestamp - active_hold_start
                trigger = config.hold_trigger_seconds
                hold_progress = min(elapsed / trigger, 1.0) if trigger > 0 else 1.0
                hold_phase_text = f"Hold: HOLDING  {elapsed:.1f}s / {trigger:.1f}s"
            else:
                hold_phase_text = "Hold: HOLDING"
            hold_phase_color = color_orange
        elif active_state == "COOLDOWN":
            hold_phase_text = "Hold: COOLDOWN"
            hold_phase_color = color_grey

    if hold_phase_text is not None:
        lines.append((hold_phase_text, hold_phase_color))

    y_offset = 20
    last_y_bottom = 20
    for text, color in lines:
        (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
        # Semi-transparent background rectangle
        cv2.rectangle(
            frame,
            (8, y_offset - th - padding),
            (8 + tw + padding * 2, y_offset + baseline + padding),
            bg_color,
            cv2.FILLED,
        )
        cv2.putText(frame, text, (8 + padding, y_offset), font, scale, color, thickness)
        last_y_bottom = y_offset + baseline + padding
        y_offset += th + baseline + padding * 2 + 4

    # Draw hold progress bar when HOLDING.
    if hold_progress is not None:
        bar_max_width = 120
        bar_height = 6
        bar_x = 8
        bar_y = last_y_bottom + 4
        # Background bar (dark grey)
        cv2.rectangle(
            frame,
            (bar_x, bar_y),
            (bar_x + bar_max_width, bar_y + bar_height),
            (60, 60, 60),
            cv2.FILLED,
        )
        # Fill bar (orange)
        fill_width = max(1, int(bar_max_width * hold_progress))
        cv2.rectangle(
            frame,
            (bar_x, bar_y),
            (bar_x + fill_width, bar_y + bar_height),
            color_orange,
            cv2.FILLED,
        )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(config: Config, dry_run: bool) -> None:
    """Open the camera, run the gesture loop, block until the user quits."""
    cap = cv2.VideoCapture(config.camera_index)
    if not cap.isOpened():
        print(f"ERROR: cannot open camera {config.camera_index}", file=sys.stderr)
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.frame_height)
    cap.set(cv2.CAP_PROP_FPS, config.target_fps)

    recognizer = build_recognizer(config)
    dispatcher = GestureDispatcher(config)
    dispatch_fn = dispatch_action_dry_run if dry_run else dispatch_action

    # FPS tracking
    fps_window = 30
    frame_times: list[float] = []
    fps: float = 0.0

    last_action: Action | None = None
    last_detection: Detection | None = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("WARNING: failed to read frame, skipping.", file=sys.stderr)
                continue

            t_start = time.monotonic()

            # Mirror the frame so that left/right swipes match user perspective.
            frame = cv2.flip(frame, 1)

            # Convert BGR -> RGB for MediaPipe.
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # MediaPipe VIDEO mode requires monotonically increasing timestamps in ms.
            timestamp_ms = int(t_start * 1000)
            result = recognizer.recognize_for_video(mp_image, timestamp_ms)

            detection = extract_detection(result, t_start)
            last_detection = detection

            action = dispatcher.update(detection)

            if action is not None:
                last_action = action
                dispatch_fn(action)
                if dry_run:
                    print(
                        f"[dry-run] gesture={detection.gesture_label!r}  "
                        f"confidence={detection.gesture_confidence:.2f}  "
                        f"action={action.name}"
                    )

            # FPS counter
            frame_times.append(t_start)
            if len(frame_times) > fps_window:
                frame_times.pop(0)
            if len(frame_times) >= 2:
                fps = (len(frame_times) - 1) / (frame_times[-1] - frame_times[0])

            hold_states = dispatcher.get_hold_states()
            draw_overlay(frame, detection, last_action, fps, hold_states=hold_states, config=config)
            cv2.imshow("Gesture Control", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        recognizer.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Gesture-controlled macOS media keys via webcam.",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=None,
        metavar="INDEX",
        help=f"Camera device index (default: {DEFAULT_CONFIG.camera_index})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        metavar="PATH",
        help=f"Path to gesture_recognizer.task (default: {DEFAULT_CONFIG.model_path})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions to stdout instead of dispatching to Hammerspoon.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Build config, applying CLI overrides where provided.
    overrides: dict[str, object] = {}
    if args.camera is not None:
        overrides["camera_index"] = args.camera
    if args.model is not None:
        overrides["model_path"] = args.model

    from dataclasses import replace
    config = replace(DEFAULT_CONFIG, **overrides) if overrides else DEFAULT_CONFIG

    # Fail early with a clear message if the model file is missing.
    if not os.path.isfile(config.model_path):
        print(
            f"ERROR: model file not found: {config.model_path}\n"
            "\n"
            "Run the download script first:\n"
            "    bash scripts/download_model.sh\n"
            "\n"
            "Or pass a custom path with --model PATH",
            file=sys.stderr,
        )
        sys.exit(1)

    run(config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
