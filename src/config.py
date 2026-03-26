from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Hold detection thresholds
    gesture_confidence_on: float = 0.7
    gesture_confidence_off: float = 0.6
    hold_stability_frames: int = 4
    hold_trigger_seconds: float = 0.8
    hold_cooldown_seconds: float = 1.2

    # Swipe detection thresholds
    swipe_window_frames: int = 14
    swipe_min_delta_x: float = 0.18
    swipe_max_delta_y: float = 0.10
    swipe_cooldown_seconds: float = 0.5

    # Pinch / volume detection thresholds
    pinch_distance_threshold: float = 0.05
    pinch_release_threshold: float = 0.08
    volume_step_delta_y: float = 0.03
    volume_cooldown_seconds: float = 0.3

    # Hand tracking
    hand_lost_reset_frames: int = 2

    # Camera settings
    camera_index: int = 0
    frame_width: int = 640
    frame_height: int = 480
    target_fps: int = 30

    # MediaPipe model
    model_path: str = "models/gesture_recognizer.task"


DEFAULT_CONFIG = Config()
