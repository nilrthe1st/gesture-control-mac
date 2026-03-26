---
name: macOS setup requirements for gesture-control-mac
description: Permissions and CLI install steps needed before the bridge works end-to-end
type: project
---

Required before the bridge works:

1. **Hammerspoon installed** — download from https://www.hammerspoon.org or `brew install --cask hammerspoon`.
2. **Accessibility permission** — System Settings > Privacy & Security > Accessibility > enable Hammerspoon. Required for `hs.eventtap` (media keys).
3. **init.lua loads the config** — add `require("gesture_control")` to `~/.hammerspoon/init.lua`, or symlink/copy `mac/gesture_control.lua` to `~/.hammerspoon/gesture_control.lua`.
4. **Reload Hammerspoon** after any Lua change: click the menubar icon > Reload Config, or run `hs -c 'hs.reload()'` from Terminal.
5. **Python `open` binary** — ships with macOS, no install needed.

**Why:** Media key injection via `hs.eventtap` requires Accessibility; without it the key events are silently dropped.

**How to apply:** Mention these steps whenever the user reports media keys not working or when setting up on a new machine.
