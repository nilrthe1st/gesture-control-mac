---
name: Hammerspoon bridge design
description: Exact bridge contract between Python and Hammerspoon for gesture-control-mac
type: project
---

Python fires `open -g hammerspoon://<command>` via `subprocess.Popen` with stdout/stderr devnull.
The `-g` flag keeps focus on the current app.

**Why:** Keeps the bridge to a single shell call; Hammerspoon's URL scheme is stable and requires no IPC socket or daemon.

**How to apply:** Do not introduce sockets, pipes, or AppleScript unless the URL scheme proves insufficient. The six command names in `ACTION_TO_COMMAND` are the stable surface — any Lua-side rename must be mirrored there.

Stable command names (Python key -> Lua bind name):
- PLAY_PAUSE   -> play_pause
- NEXT_TRACK   -> next_track
- PREV_TRACK   -> prev_track
- VOLUME_UP    -> volume_up
- VOLUME_DOWN  -> volume_down
- MUTE_TOGGLE  -> mute_toggle

Lua media key names: "PLAY", "NEXT", "PREVIOUS" (not "PREV").
Volume clamped: max 100, min 0. Steps are +/- 5.
Mute: `device:setMuted(not device:muted())`.
