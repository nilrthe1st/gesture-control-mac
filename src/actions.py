from enum import Enum, auto


class Action(Enum):
    PLAY_PAUSE = auto()
    NEXT_TRACK = auto()
    PREV_TRACK = auto()
    VOLUME_UP = auto()
    VOLUME_DOWN = auto()
    MUTE_TOGGLE = auto()


# Maps each Action to the Hammerspoon URL command name.
# The bridge calls: open -g hammerspoon://<command>
ACTION_TO_COMMAND: dict[Action, str] = {
    Action.PLAY_PAUSE: "play_pause",
    Action.NEXT_TRACK: "next_track",
    Action.PREV_TRACK: "prev_track",
    Action.VOLUME_UP: "volume_up",
    Action.VOLUME_DOWN: "volume_down",
    Action.MUTE_TOGGLE: "mute_toggle",
}
