-- gesture_control.lua
-- Load from your Hammerspoon init.lua with:
--   require("gesture_control")
--
-- Each gesture fires a URL event via:
--   open -g hammerspoon://<command>
-- Python side: src/hammerspoon_bridge.py

local log = hs.logger.new("gesture")
log:i("gesture_control.lua loaded")


-- Helper: send a system media key (press then immediate release).
local function sendMediaKey(keyname)
    hs.eventtap.event.newSystemKeyEvent(keyname, true):post()
    hs.eventtap.event.newSystemKeyEvent(keyname, false):post()
end


hs.urlevent.bind("play_pause", function(eventName, params)
    sendMediaKey("PLAY")
    hs.alert.show("▶ Play/Pause")
end)

hs.urlevent.bind("next_track", function(eventName, params)
    sendMediaKey("NEXT")
    hs.alert.show("⏭ Next")
end)

hs.urlevent.bind("prev_track", function(eventName, params)
    sendMediaKey("PREVIOUS")
    hs.alert.show("⏮ Prev")
end)

hs.urlevent.bind("volume_up", function(eventName, params)
    local device = hs.audiodevice.defaultOutputDevice()
    if device then
        local current = device:volume() or 0
        local next = math.min(current + 5, 100)
        device:setVolume(next)
    end
    hs.alert.show("🔊 Vol +5")
end)

hs.urlevent.bind("volume_down", function(eventName, params)
    local device = hs.audiodevice.defaultOutputDevice()
    if device then
        local current = device:volume() or 0
        local next = math.max(current - 5, 0)
        device:setVolume(next)
    end
    hs.alert.show("🔉 Vol -5")
end)

hs.urlevent.bind("mute_toggle", function(eventName, params)
    local device = hs.audiodevice.defaultOutputDevice()
    if device then
        device:setMuted(not device:muted())
    end
    hs.alert.show("🔇 Mute toggle")
end)
