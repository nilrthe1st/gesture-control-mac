---
name: implement-gesture-feature
description: Implement a scoped feature in the gesture-control app with deep reasoning, subagent delegation, and verification.
---

ultrathink.

Task: $ARGUMENTS

Rules:
- first read CLAUDE.md and the minimum relevant files
- if MediaPipe/camera/gesture logic is involved, delegate to vision-engineer
- if Hammerspoon/macOS bridge work is involved, delegate to macos-automation
- after changes, delegate review to qa-reviewer
- run the narrowest meaningful verification
- report exactly what passed, what failed, and what remains manual
