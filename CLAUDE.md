# Claude Light

Physical "Claude is waiting on you" indicator: an ESP32-S3 + WS2812 LED on home
Wi-Fi, driven by Claude Code hooks. Colour = why Claude is waiting
(purple question, amber permission, blue finished); animation escalates with
time waiting. Full design: `docs/superpowers/specs/2026-11-03-claude-light-design.md`.

## Layout

- `board/` — MicroPython firmware files uploaded to the ESP32-S3.
  `sessions.py` and `animate.py` must stay hardware-free (no `machine`,
  `neopixel`, `network` imports) so they run under CPython for tests.
- `hooks/claude_light_hook.py` — Claude Code hook (stdlib-only Python). Must
  always exit 0, print nothing, and time out within ~1 s.
- `tests/` — pytest unit tests, run on the PC.

## Hardware facts

- ESP32-S3 N16R8 (16 MB flash, 8 MB **octal** PSRAM), DevKitC-1 clone, "HW-678".
- WS2812 LED on **GPIO48**. GPIO35/36/37 are wired to PSRAM — never use them.
- GPIO0 = BOOT button. GPIO41/42 reserved for an optional SSD1306 OLED.
- MicroPython build: `ESP32_GENERIC_S3`, `SPIRAM_OCT` variant.
- Use the board's **native USB** port (shows as "USB Serial Device", VID 303A;
  was COM5). The CH343 "UART" port did not respond.
- PC USB power browns the board out once Wi-Fi is on. Flash/upload over PC USB,
  but run it from a USB charger (or a rear port / powered hub + good cable).

## Commands

- Tests: `python -m pytest`
- Upload files: `mpremote connect COM5 cp -r board/. :` (check the COM port first)
- Serial REPL: `mpremote connect COM5`
- Board debug: `curl http://claude-light.local/`
- Fake event: `curl -X POST http://claude-light.local/event -d '{"session":"t1","state":"question"}'`

## Rules

- `board/secrets.py` holds Wi-Fi credentials — git-ignored, never commit it or
  echo its contents. `board/secrets.example.py` is the template.
- Tunable thresholds/colours live only in `board/config.py`.
