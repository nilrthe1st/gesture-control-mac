"""
Pure logic tests for src/gesture_engine.py.

No camera, no MediaPipe, no OS calls.

Time is controlled explicitly via Detection.timestamp so tests are
deterministic regardless of wall-clock speed.
"""

from __future__ import annotations

import pytest

from src.actions import Action
from src.config import Config
from src.gesture_engine import GestureDispatcher, HoldDetector, PinchDragDetector, SwipeDetector
from tests.conftest import make_detection, make_no_hand



# ---------------------------------------------------------------------------
# HoldDetector tests (fully implemented — must all pass)
# ---------------------------------------------------------------------------

class TestHoldDetector:

    def test_hold_fires_after_stability_and_time(self, fast_config: Config) -> None:
        """
        After hold_stability_frames frames of a matching gesture, the action
        should fire on the first frame whose timestamp satisfies
        elapsed >= hold_trigger_seconds.

        fast_config has hold_trigger_seconds=0.0, so any frame after HOLDING
        state is entered fires immediately.
        """
        detector = HoldDetector("Open_Palm", Action.PLAY_PAUSE, fast_config)
        t = 0.0

        # Feed stability frames to reach HOLDING
        for _ in range(fast_config.hold_stability_frames):
            result = detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
            assert result is None, "No action should fire during STABILIZING"
            t += 0.033

        # The very next frame should fire because hold_trigger_seconds=0.0
        result = detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        assert result is Action.PLAY_PAUSE

    def test_hold_resets_on_gesture_break(self, fast_config: Config) -> None:
        """
        If a different gesture appears during STABILIZING, the detector should
        return to IDLE and not fire.
        """
        detector = HoldDetector("Open_Palm", Action.PLAY_PAUSE, fast_config)
        t = 0.0

        # Start stabilizing (but don't complete it)
        detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        t += 0.033

        # Break with a different label
        result = detector.update(make_detection(gesture_label="Closed_Fist", timestamp=t))
        assert result is None

        # Feed full stability frames — should need to restart from scratch
        t += 0.033
        for _ in range(fast_config.hold_stability_frames):
            result = detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
            t += 0.033
        # After the loop the detector is HOLDING; the next frame fires
        result = detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        assert result is Action.PLAY_PAUSE

    def test_hold_cooldown_blocks_retrigger(self) -> None:
        """
        After firing once, a non-zero cooldown should block a second fire on
        the very next frame.  Use a custom config with a positive cooldown.
        """
        cfg = Config(
            hold_stability_frames=2,
            hold_trigger_seconds=0.0,
            hold_cooldown_seconds=1.2,  # non-zero
        )
        detector = HoldDetector("Open_Palm", Action.PLAY_PAUSE, cfg)
        t = 0.0

        # Reach HOLDING and fire
        for _ in range(cfg.hold_stability_frames):
            detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
            t += 0.033
        first = detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        assert first is Action.PLAY_PAUSE

        # Immediately try to retrigger — cooldown has not expired (only ~0ms elapsed)
        t += 0.001
        second = detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        assert second is None, "Cooldown should block retrigger"

    def test_hold_below_confidence_on_threshold(self, fast_config: Config) -> None:
        """
        A confidence of 0.65 is below gesture_confidence_on=0.7, so the
        detector must remain in IDLE and never fire.
        """
        detector = HoldDetector("Open_Palm", Action.PLAY_PAUSE, fast_config)
        t = 0.0
        for _ in range(fast_config.hold_stability_frames + 2):
            result = detector.update(
                make_detection(gesture_label="Open_Palm", gesture_confidence=0.65, timestamp=t)
            )
            assert result is None
            t += 0.033

    def test_fist_fires_mute_toggle(self, fast_config: Config) -> None:
        """Closed_Fist hold should fire MUTE_TOGGLE after stability + trigger."""
        detector = HoldDetector("Closed_Fist", Action.MUTE_TOGGLE, fast_config)
        t = 0.0

        # Feed stability frames to reach HOLDING
        for _ in range(fast_config.hold_stability_frames):
            result = detector.update(make_detection(gesture_label="Closed_Fist", timestamp=t))
            assert result is None, "No action should fire during STABILIZING"
            t += 0.033

        # With hold_trigger_seconds=0.0 the very next frame fires
        result = detector.update(make_detection(gesture_label="Closed_Fist", timestamp=t))
        assert result is Action.MUTE_TOGGLE

    def test_fist_cooldown_blocks_retrigger(self) -> None:
        """After MUTE_TOGGLE fires, non-zero cooldown must block immediate retrigger."""
        cfg = Config(
            hold_stability_frames=2,
            hold_trigger_seconds=0.0,
            hold_cooldown_seconds=1.2,
        )
        detector = HoldDetector("Closed_Fist", Action.MUTE_TOGGLE, cfg)
        t = 0.0

        # Reach HOLDING and fire
        for _ in range(cfg.hold_stability_frames):
            detector.update(make_detection(gesture_label="Closed_Fist", timestamp=t))
            t += 0.033
        first = detector.update(make_detection(gesture_label="Closed_Fist", timestamp=t))
        assert first is Action.MUTE_TOGGLE

        # Immediately attempt retrigger — cooldown has not expired
        t += 0.001
        second = detector.update(make_detection(gesture_label="Closed_Fist", timestamp=t))
        assert second is None, "Cooldown should block immediate retrigger"

    def test_hold_detector_exposes_state_name(self, fast_config: Config) -> None:
        """state_name property should reflect the FSM state at each transition."""
        detector = HoldDetector("Open_Palm", Action.PLAY_PAUSE, fast_config)
        t = 0.0

        # Initially IDLE
        assert detector.state_name == "IDLE"

        # First matching frame -> STABILIZING
        detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        t += 0.033
        assert detector.state_name == "STABILIZING"

        # Complete stability frames -> HOLDING
        # fast_config.hold_stability_frames == 2; one frame already counted above
        for _ in range(fast_config.hold_stability_frames - 1):
            detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
            t += 0.033
        assert detector.state_name == "HOLDING"

        # Trigger (hold_trigger_seconds=0.0) -> COOLDOWN
        detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        assert detector.state_name == "COOLDOWN"

    def test_hold_detector_exposes_hold_start(self, fast_config: Config) -> None:
        """hold_start should be 0.0 until HOLDING is entered, then set to the frame timestamp."""
        detector = HoldDetector("Open_Palm", Action.PLAY_PAUSE, fast_config)
        t = 0.0

        assert detector.hold_start == 0.0, "Should be 0.0 in IDLE"

        # Enter STABILIZING
        detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        t += 0.033
        assert detector.hold_start == 0.0, "Should still be 0.0 in STABILIZING"

        # Complete stability frames to reach HOLDING; the last stabilizing frame
        # sets _hold_start to its timestamp.
        for _ in range(fast_config.hold_stability_frames - 1):
            detector.update(make_detection(gesture_label="Open_Palm", timestamp=t))
            t += 0.033
        # Now in HOLDING: hold_start should equal the timestamp of the frame that
        # pushed stable_frames over the threshold (i.e. t - 0.033).
        expected_hold_start = t - 0.033
        assert detector.state_name == "HOLDING"
        assert abs(detector.hold_start - expected_hold_start) < 1e-9

    def test_hold_hysteresis_on_break(self, fast_config: Config) -> None:
        """
        Hysteresis rules:
          - confidence 0.65 (between off=0.6 and on=0.7) during STABILIZING
            should NOT break the gesture (stays in STABILIZING).
          - confidence 0.55 (below off=0.6) during STABILIZING
            SHOULD break the gesture (returns to IDLE).

        We verify by observing whether the hold eventually fires.
        """
        # --- Case 1: mid-band confidence keeps stabilizing ---
        cfg = fast_config
        detector = HoldDetector("Open_Palm", Action.PLAY_PAUSE, cfg)
        t = 0.0

        # First frame: above ON threshold -> enter STABILIZING
        detector.update(make_detection(gesture_label="Open_Palm", gesture_confidence=0.9, timestamp=t))
        t += 0.033

        # Second frame: mid-band (0.65) — should stay in STABILIZING (not break)
        # With hold_stability_frames=2 we've now incremented stable_frames twice,
        # so this frame should push us into HOLDING.
        detector.update(
            make_detection(gesture_label="Open_Palm", gesture_confidence=0.65, timestamp=t)
        )
        t += 0.033

        # Next frame triggers because we're in HOLDING and hold_trigger_seconds=0.0
        result = detector.update(
            make_detection(gesture_label="Open_Palm", gesture_confidence=0.9, timestamp=t)
        )
        assert result is Action.PLAY_PAUSE, (
            "Mid-band confidence (0.65) should NOT break stabilizing"
        )

        # --- Case 2: below OFF threshold breaks stabilizing ---
        detector.reset()
        t = 0.0

        # Enter STABILIZING
        detector.update(make_detection(gesture_label="Open_Palm", gesture_confidence=0.9, timestamp=t))
        t += 0.033

        # Below OFF threshold -> should break back to IDLE
        result = detector.update(
            make_detection(gesture_label="Open_Palm", gesture_confidence=0.55, timestamp=t)
        )
        assert result is None
        t += 0.033

        # If we're truly back in IDLE we need a full stability cycle again.
        # Feed only 1 frame (less than hold_stability_frames=2) — should still be None.
        result = detector.update(
            make_detection(gesture_label="Open_Palm", gesture_confidence=0.9, timestamp=t)
        )
        assert result is None, (
            "After confidence-break detector should be in IDLE/STABILIZING, not yet HOLDING"
        )


# ---------------------------------------------------------------------------
# SwipeDetector tests
# ---------------------------------------------------------------------------

class TestSwipeDetector:

    def test_swipe_right_fires_next_track(self, fast_config: Config) -> None:
        detector = SwipeDetector(fast_config)
        t = 0.0
        # Move wrist from x=0.1 to x=0.4 over swipe_window_frames frames
        n = fast_config.swipe_window_frames
        for i in range(n):
            x = 0.1 + 0.3 * (i / (n - 1))
            result = detector.update(
                make_detection(gesture_label="None", wrist_x=x, timestamp=t)
            )
            t += 0.033
        assert result is Action.NEXT_TRACK

    def test_swipe_left_fires_prev_track(self, fast_config: Config) -> None:
        detector = SwipeDetector(fast_config)
        t = 0.0
        n = fast_config.swipe_window_frames
        for i in range(n):
            x = 0.9 - 0.3 * (i / (n - 1))
            result = detector.update(
                make_detection(gesture_label="None", wrist_x=x, timestamp=t)
            )
            t += 0.033
        assert result is Action.PREV_TRACK

    def test_swipe_diagonal_rejected(self, fast_config: Config) -> None:
        """
        A motion with large delta_y should NOT fire (exceeds swipe_max_delta_y).
        """
        detector = SwipeDetector(fast_config)
        t = 0.0
        n = fast_config.swipe_window_frames
        fired = False
        for i in range(n):
            x = 0.1 + 0.3 * (i / (n - 1))
            y = 0.1 + 0.3 * (i / (n - 1))  # diagonal motion
            result = detector.update(
                make_detection(gesture_label="None", wrist_x=x, wrist_y=y, timestamp=t)
            )
            if result is not None:
                fired = True
            t += 0.033
        assert not fired

    def test_swipe_too_small_ignored(self, fast_config: Config) -> None:
        """
        A motion below swipe_min_delta_x should NOT fire.
        """
        detector = SwipeDetector(fast_config)
        t = 0.0
        n = fast_config.swipe_window_frames
        fired = False
        for i in range(n):
            x = 0.5 + 0.05 * (i / (n - 1))  # tiny motion
            result = detector.update(
                make_detection(gesture_label="None", wrist_x=x, timestamp=t)
            )
            if result is not None:
                fired = True
            t += 0.033
        assert not fired


# ---------------------------------------------------------------------------
# PinchDragDetector tests
# ---------------------------------------------------------------------------

class TestPinchDragDetector:

    def test_pinch_drag_up_fires_volume_up(self, fast_config: Config) -> None:
        detector = PinchDragDetector(fast_config)
        t = 0.0
        # Enter pinch: thumb and index very close
        result = detector.update(
            make_detection(
                thumb_tip_x=0.5, thumb_tip_y=0.5,
                index_tip_x=0.52, index_tip_y=0.52,
                wrist_y=0.6, timestamp=t,
            )
        )
        t += 0.033
        # Drag up (y decreases in image coords)
        result = detector.update(
            make_detection(
                thumb_tip_x=0.5, thumb_tip_y=0.5,
                index_tip_x=0.52, index_tip_y=0.52,
                wrist_y=0.55, timestamp=t,  # delta_y = 0.05 >= 0.03
            )
        )
        assert result is Action.VOLUME_UP

    def test_pinch_drag_down_fires_volume_down(self, fast_config: Config) -> None:
        detector = PinchDragDetector(fast_config)
        t = 0.0
        result = detector.update(
            make_detection(
                thumb_tip_x=0.5, thumb_tip_y=0.5,
                index_tip_x=0.52, index_tip_y=0.52,
                wrist_y=0.4, timestamp=t,
            )
        )
        t += 0.033
        result = detector.update(
            make_detection(
                thumb_tip_x=0.5, thumb_tip_y=0.5,
                index_tip_x=0.52, index_tip_y=0.52,
                wrist_y=0.45, timestamp=t,  # delta_y = -0.05, below anchor
            )
        )
        assert result is Action.VOLUME_DOWN

    def test_pinch_release_during_cooldown_step_resets_to_idle(self, fast_config: Config) -> None:
        """
        Releasing the pinch while in COOLDOWN_STEP should immediately transition
        to IDLE, not wait for cooldown to expire and re-enter PINCHING.
        """
        cfg = Config(
            pinch_distance_threshold=0.05,
            pinch_release_threshold=0.08,
            volume_step_delta_y=0.03,
            volume_cooldown_seconds=1.0,  # long cooldown so COOLDOWN_STEP is active
        )
        detector = PinchDragDetector(cfg)
        t = 0.0
        # Enter PINCHING
        detector.update(make_detection(
            thumb_tip_x=0.5, thumb_tip_y=0.5,
            index_tip_x=0.52, index_tip_y=0.52,
            wrist_y=0.6, timestamp=t,
        ))
        t += 0.033
        # Fire VOLUME_UP -> enter COOLDOWN_STEP
        r = detector.update(make_detection(
            thumb_tip_x=0.5, thumb_tip_y=0.5,
            index_tip_x=0.52, index_tip_y=0.52,
            wrist_y=0.55, timestamp=t,  # delta_y = 0.05 >= 0.03
        ))
        assert r is Action.VOLUME_UP
        assert detector.state_name == "COOLDOWN_STEP"
        t += 0.033
        # Release pinch during COOLDOWN_STEP (distance >> threshold)
        r = detector.update(make_detection(
            thumb_tip_x=0.5, thumb_tip_y=0.5,
            index_tip_x=0.7, index_tip_y=0.7,  # distance ≈ 0.28 > release threshold
            wrist_y=0.55, timestamp=t,
        ))
        assert r is None
        assert detector.state_name == "IDLE"

    def test_pinch_release_resets_to_idle(self, fast_config: Config) -> None:
        """
        Releasing the pinch (distance > pinch_release_threshold) should reset
        the detector to IDLE, so the next pinch starts fresh.
        """
        detector = PinchDragDetector(fast_config)
        t = 0.0
        # Enter pinch
        detector.update(
            make_detection(
                thumb_tip_x=0.5, thumb_tip_y=0.5,
                index_tip_x=0.52, index_tip_y=0.52,
                timestamp=t,
            )
        )
        t += 0.033
        # Release pinch
        result = detector.update(
            make_detection(
                thumb_tip_x=0.5, thumb_tip_y=0.5,
                index_tip_x=0.7, index_tip_y=0.7,  # far apart
                timestamp=t,
            )
        )
        assert result is None
        t += 0.033
        # Should be in IDLE again — a small vertical movement after release must
        # not fire a volume action.
        result = detector.update(
            make_detection(
                thumb_tip_x=0.5, thumb_tip_y=0.5,
                index_tip_x=0.7, index_tip_y=0.7,
                wrist_y=0.3, timestamp=t,
            )
        )
        assert result is None


# ---------------------------------------------------------------------------
# GestureDispatcher tests (fully implemented — must all pass)
# ---------------------------------------------------------------------------

class TestGestureDispatcher:

    def test_dispatcher_hand_loss_resets_detectors(self, fast_config: Config) -> None:
        """
        If the hand is lost for >= hand_lost_reset_frames consecutive frames,
        all sub-detectors should reset.  After reset the hold detector must
        require a full new stability cycle.
        """
        dispatcher = GestureDispatcher(fast_config)
        t = 0.0

        # Partially stabilize (one frame less than required to reach HOLDING)
        partial_frames = fast_config.hold_stability_frames - 1
        for _ in range(partial_frames):
            dispatcher.update(make_detection(gesture_label="Open_Palm", timestamp=t))
            t += 0.033

        # Lose the hand for exactly hand_lost_reset_frames frames
        for _ in range(fast_config.hand_lost_reset_frames):
            dispatcher.update(make_no_hand(timestamp=t))
            t += 0.033

        # Now resume the gesture — we should need a fresh full stability cycle.
        # Feed hold_stability_frames - 1 frames (one short): must still be None.
        for _ in range(fast_config.hold_stability_frames - 1):
            result = dispatcher.update(
                make_detection(gesture_label="Open_Palm", timestamp=t)
            )
            assert result is None, "Should not fire before completing a fresh stability cycle"
            t += 0.033

        # Feed the final stability frame + one more to trigger
        dispatcher.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        t += 0.033
        result = dispatcher.update(make_detection(gesture_label="Open_Palm", timestamp=t))
        assert result is Action.PLAY_PAUSE

    def test_dispatcher_returns_none_with_no_hand(self, fast_config: Config) -> None:
        """No-hand frames must always return None."""
        dispatcher = GestureDispatcher(fast_config)
        for i in range(5):
            result = dispatcher.update(make_no_hand(timestamp=float(i) * 0.033))
            assert result is None

    def test_dispatcher_hold_palm_fires(self, fast_config: Config) -> None:
        """
        End-to-end: feeding hold_stability_frames + 1 Open_Palm frames through
        the dispatcher should yield Action.PLAY_PAUSE on the last frame.
        """
        dispatcher = GestureDispatcher(fast_config)
        t = 0.0
        last_result: Action | None = None

        # hold_stability_frames frames to enter HOLDING, then one more to fire
        total_frames = fast_config.hold_stability_frames + 1
        for i in range(total_frames):
            result = dispatcher.update(
                make_detection(gesture_label="Open_Palm", timestamp=t)
            )
            if result is not None:
                last_result = result
            t += 0.033

        assert last_result is Action.PLAY_PAUSE

    def test_dispatcher_fist_hold_fires_mute(self, fast_config: Config) -> None:
        """
        End-to-end: feeding hold_stability_frames + 1 Closed_Fist frames through
        the dispatcher should yield Action.MUTE_TOGGLE on the last frame.
        """
        dispatcher = GestureDispatcher(fast_config)
        t = 0.0
        last_result: Action | None = None

        total_frames = fast_config.hold_stability_frames + 1
        for _ in range(total_frames):
            result = dispatcher.update(
                make_detection(gesture_label="Closed_Fist", timestamp=t)
            )
            if result is not None:
                last_result = result
            t += 0.033

        assert last_result is Action.MUTE_TOGGLE

    def test_dispatcher_get_hold_states_returns_state(self, fast_config: Config) -> None:
        """
        get_hold_states() should return a dict with 'palm' and 'fist' keys, each
        containing 'state' and 'hold_start'.  The state should reflect which
        detector is active as frames are fed.
        """
        dispatcher = GestureDispatcher(fast_config)
        t = 0.0

        # Initially both should be IDLE
        states = dispatcher.get_hold_states()
        assert states["palm"]["state"] == "IDLE"
        assert states["fist"]["state"] == "IDLE"
        assert states["palm"]["hold_start"] == 0.0
        assert states["fist"]["hold_start"] == 0.0

        # Feed one Closed_Fist frame -> fist detector enters STABILIZING
        dispatcher.update(make_detection(gesture_label="Closed_Fist", timestamp=t))
        t += 0.033
        states = dispatcher.get_hold_states()
        assert states["palm"]["state"] == "IDLE"
        assert states["fist"]["state"] == "STABILIZING"

        # Feed enough frames to reach HOLDING
        for _ in range(fast_config.hold_stability_frames - 1):
            dispatcher.update(make_detection(gesture_label="Closed_Fist", timestamp=t))
            t += 0.033
        states = dispatcher.get_hold_states()
        assert states["fist"]["state"] == "HOLDING"
        assert states["fist"]["hold_start"] > 0.0

        # Trigger the action (hold_trigger_seconds=0.0) -> COOLDOWN
        dispatcher.update(make_detection(gesture_label="Closed_Fist", timestamp=t))
        t += 0.033
        states = dispatcher.get_hold_states()
        assert states["fist"]["state"] == "COOLDOWN"
        assert states["fist"]["hold_start"] > 0.0, "hold_start must remain set in COOLDOWN"

    def test_dispatcher_get_dynamic_states(self, fast_config: Config) -> None:
        """get_dynamic_states() should return swipe and pinch state names."""
        dispatcher = GestureDispatcher(fast_config)
        states = dispatcher.get_dynamic_states()
        assert states["swipe"] == "TRACKING"
        assert states["pinch"] == "IDLE"


# ---------------------------------------------------------------------------
# SwipeDetector — cooldown test (needs a separate Config with positive cooldown)
# ---------------------------------------------------------------------------

class TestSwipeDetectorCooldown:

    def test_swipe_cooldown_blocks_immediate_retrigger(self) -> None:
        """After a swipe fires, COOLDOWN blocks a second fire until it expires."""
        cfg = Config(
            swipe_window_frames=14,
            swipe_min_delta_x=0.18,
            swipe_max_delta_y=0.10,
            swipe_cooldown_seconds=1.0,  # non-zero
        )
        detector = SwipeDetector(cfg)
        n = cfg.swipe_window_frames
        t = 0.0

        # First right swipe — should fire on the 14th frame.
        first_result = None
        for i in range(n):
            x = 0.1 + 0.3 * (i / (n - 1))
            r = detector.update(make_detection(wrist_x=x, wrist_y=0.5, timestamp=t))
            if r is not None:
                first_result = r
            t += 0.033
        assert first_result is Action.NEXT_TRACK

        # Immediately attempt a second right swipe — deque was cleared, only ~0.46s elapsed.
        second_result = None
        for i in range(n):
            x = 0.1 + 0.3 * (i / (n - 1))
            r = detector.update(make_detection(wrist_x=x, wrist_y=0.5, timestamp=t))
            if r is not None:
                second_result = r
            t += 0.033
        assert second_result is None, "Cooldown should block immediate retrigger"


# ---------------------------------------------------------------------------
# PinchDragDetector — incremental multi-step test
# ---------------------------------------------------------------------------

class TestPinchDragDetectorIncremental:

    def test_pinch_multi_step_incremental(self, fast_config: Config) -> None:
        """Each upward step fires VOLUME_UP independently; anchor updates after each step."""
        detector = PinchDragDetector(fast_config)  # volume_cooldown_seconds=0.0
        t = 0.0

        # Enter pinch: distance ≈ 0.028 < threshold 0.05; anchor_y set to 0.60.
        detector.update(make_detection(
            thumb_tip_x=0.5, thumb_tip_y=0.5,
            index_tip_x=0.52, index_tip_y=0.52,
            wrist_y=0.60, timestamp=t,
        ))
        t += 0.033

        # Step 1: move up by 0.04 (> threshold 0.03, avoids float rounding on boundary).
        r1 = detector.update(make_detection(
            thumb_tip_x=0.5, thumb_tip_y=0.5,
            index_tip_x=0.52, index_tip_y=0.52,
            wrist_y=0.56, timestamp=t,   # delta = 0.60 - 0.56 = 0.04
        ))
        t += 0.033
        assert r1 is Action.VOLUME_UP

        # The COOLDOWN_STEP handler transitions to PINCHING and returns None on the
        # frame that expires cooldown; volume is checked on the *next* PINCHING frame.
        # Frame 3: COOLDOWN_STEP → PINCHING (returns None; anchor stays at 0.56).
        r_transition = detector.update(make_detection(
            thumb_tip_x=0.5, thumb_tip_y=0.5,
            index_tip_x=0.52, index_tip_y=0.52,
            wrist_y=0.56, timestamp=t,   # same as anchor; no step yet
        ))
        t += 0.033
        assert r_transition is None

        # Frame 4: PINCHING, anchor=0.56; move up another 0.04 → fire VOLUME_UP.
        r2 = detector.update(make_detection(
            thumb_tip_x=0.5, thumb_tip_y=0.5,
            index_tip_x=0.52, index_tip_y=0.52,
            wrist_y=0.52, timestamp=t,   # delta = 0.56 - 0.52 = 0.04
        ))
        assert r2 is Action.VOLUME_UP
