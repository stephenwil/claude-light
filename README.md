# Claude Light

An ESP32-S3 with a WS2812 LED that lights up when Claude Code is waiting on you.

## Why

Claude Code often works for minutes at a time, so it's natural to switch to
something else while it runs. The catch is that it regularly stops and waits
for you: to answer a question, to approve a command, or because it has
finished. Unless you keep checking the terminal, that waiting time is lost,
and with several sessions open it's easy to forget one entirely.

Claude Light moves that signal off the screen and onto your desk. One glance
tells you whether Claude is waiting, why, and roughly for how long. The longer
it's ignored, the more "agitated" it looks, so a session that's been stuck for
twenty minutes is hard to miss. When nothing needs you, it stays dark.

It's also a small, complete example of wiring Claude Code
[hooks](https://code.claude.com/docs/en/hooks) to physical hardware.

## What it shows

- **Colour = why:** purple question, amber permission prompt, blue finished.
- **Animation = how long:** calm breathing (0–1 min) → nudging (1–5) →
  agitated pulses (5–15) → frantic strobe drifting to red (15+).
- Several sessions? It shows the longest-waiting one and double-blinks.
- Faint white blip every 3 s = board is offline from Wi-Fi.

Design: `docs/superpowers/specs/2026-11-03-claude-light-design.md`.
Shareable guide to the light: `docs/infographic.html`.

## How it works

```
Claude Code hook ──HTTP POST──▶ claude-light.local (ESP32 on Wi-Fi) ──▶ LED
```

Claude Code runs `hooks/claude_light_hook.py` when it asks a question, needs
permission, finishes, or when you respond. The hook sends a tiny JSON event to
the board over your home Wi-Fi and returns immediately, so Claude Code is never
slowed down. The board, running MicroPython, keeps a table of waiting sessions
and animates the LED for the one that has waited longest. It advertises itself
by mDNS as `claude-light.local`, so you don't need its IP address.

## The board

Any ESP32-S3 board with a WS2812 ("NeoPixel") RGB LED should work. This was
built on a common, inexpensive **ESP32-S3-DevKitC-1 clone, N16R8 variant**:

| | |
|---|---|
| Chip | ESP32-S3, dual-core 240 MHz, Wi-Fi 2.4 GHz + Bluetooth 5 LE |
| Memory | 16 MB flash, 8 MB octal PSRAM ("N16R8") |
| LED | onboard WS2812 RGB on **GPIO48** |
| USB | two USB-C ports: native USB (use this one) and a CH343 USB-UART |

Things worth knowing about this board:

- **Use the native USB port** (it appears as "USB Serial Device", Espressif
  VID 303A) for flashing and the MicroPython REPL.
- **Flash the `SPIRAM_OCT` MicroPython build.** The 8 MB PSRAM is octal;
  the plain build won't use it.
- **GPIO35, 36 and 37 are wired to the PSRAM.** Don't use them for anything else.
- **Power:** once Wi-Fi is on, the chip draws short current spikes of
  300–500 mA. Some PC USB ports (especially front-panel ports, hubs or long
  thin cables) sag enough to trip the brownout detector and reset it in a
  loop. A phone charger or a rear motherboard port with a short cable fixes it.
- Ours shipped with a manufacturer's self-test sketch ("HW-678" mass-production
  test) that runs a Wi-Fi hotspot and a test web page. Flashing MicroPython
  replaces it.

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
