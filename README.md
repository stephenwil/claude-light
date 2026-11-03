# Claude Light

An ESP32-S3 with a WS2812 LED that lights up when Claude Code is waiting on you.

- **Colour = why:** purple question, amber permission prompt, blue finished.
- **Animation = how long:** calm breathing (0–1 min) → nudging (1–5) →
  agitated pulses (5–15) → frantic strobe drifting to red (15+).
- Several sessions? It shows the longest-waiting one and double-blinks.
- Faint white blip every 3 s = board is offline from Wi-Fi.

Design: `docs/superpowers/specs/2026-11-03-claude-light-design.md`.
Shareable guide to the light: `docs/infographic.html`.

## Hardware

ESP32-S3 N16R8 dev board (DevKitC-1 clone). WS2812 on GPIO48. Run it from a
USB charger; some PC USB ports can't supply the Wi-Fi current spikes.

## Setup

1. Flash MicroPython (`ESP32_GENERIC_S3`, **SPIRAM_OCT** build) with esptool:
   `python -m esptool --chip esp32s3 --port COMx erase-flash`, then
   `python -m esptool --chip esp32s3 --port COMx write-flash -z 0 firmware.bin`.
2. Copy `board/secrets.example.py` to `board/secrets.py` and fill in your
   2.4 GHz Wi-Fi name and password (git-ignored).
3. Upload: `pip install mpremote`, then
   `mpremote connect COMx cp board/config.py board/animate.py board/sessions.py board/led.py board/net.py board/server.py board/main.py board/secrets.py : + reset`
4. Check: `curl http://claude-light.local/` → `{"sessions": {}, ...}`
5. Add the hooks to `~/.claude/settings.json` (paths to your Python and this
   repo), each as `{"type": "command", "async": true, "command": "\"<python>\" \"<repo>/hooks/claude_light_hook.py\""}`:
   `PreToolUse` (matcher `AskUserQuestion`), `Notification` (matcher
   `permission_prompt`), `Stop`, `UserPromptSubmit`, `PostToolUse` (matcher `*`),
   `SessionEnd`.

## Turning it off

- `~/.claude/claude-light.off` exists, or `CLAUDE_LIGHT=off` → hook does nothing.
- Board unreachable → hook backs off for 60 s automatically; Claude Code is
  never slowed.
- Board at a fixed IP instead of mDNS: set `CLAUDE_LIGHT_URL=http://<ip>/event`.

## Tests

`python -m pytest` (pure logic and the hook; no hardware needed).
