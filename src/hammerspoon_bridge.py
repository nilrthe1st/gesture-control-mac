import logging
import subprocess

from src.actions import Action, ACTION_TO_COMMAND

logger = logging.getLogger(__name__)


def dispatch_action(action: Action) -> None:
    """Look up the Hammerspoon URL command for action and fire it via `open -g`.

    Uses the -g flag so the focused window does not change.  Any OSError
    (e.g. `open` not found, Hammerspoon not installed) is caught and logged
    as a warning so the calling loop never crashes.
    """
    command = ACTION_TO_COMMAND[action]
    try:
        subprocess.Popen(
            ["open", "-g", f"hammerspoon://{command}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.warning("Failed to dispatch action %s (command=%s): %s", action, command, exc)


def dispatch_action_dry_run(action: Action) -> None:
    """Print the URL that would be fired, without invoking any subprocess."""
    command = ACTION_TO_COMMAND[action]
    print(f"[DRY-RUN] Would fire: hammerspoon://{command}")
