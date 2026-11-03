# Claude Light — design

Date: 2026-11-03
Status: approved in conversation, awaiting written-spec review

## Purpose

A physical "Claude is waiting on you" indicator. An ESP32-S3 dev board with a
WS2812 RGB LED sits anywhere on the home Wi-Fi. When a Claude Code session needs
the user, the LED lights in a colour that says *why*, and becomes more
"agitated" the longer the user takes to respond. Glancing at it answers: is
Claude waiting, why, and for how long?

## Hardware

- ESP32-S3 (QFN56, rev v0.2), 16 MB flash, 8 MB octal PSRAM ("N16R8",
  DevKitC-1 clone, silkscreen HW-678).
- WS2812 on **GPIO48**. GPIO35–37 are used by PSRAM and must not be touched.
- Runs from a USB charger. PC USB ports brown it out once Wi-Fi is active;
  PC USB is only used for flashing / file upload.
- Firmware: MicroPython, `ESP32_GENERIC_S3` board, `SPIRAM_OCT` variant.

## Behaviour

### Reasons (base colour)

| Reason | Trigger | Colour |
|---|---|---|
| `question` | Claude asked a question (`AskUserQuestion`) | purple |
| `permission` | Claude needs permission to run a tool | amber |
| `finished` | Claude finished its turn and is idle | blue |

### Agitation stages (by time waiting)

| Stage | Waiting | Brightness | Animation |
|---|---|---|---|
| calm | 0–1 min | dim | slow breathing, ~4 s period |
| nudging | 1–5 min | medium | breathing, ~1.5 s period |
| agitated | 5–15 min | bright | pulses, ~2 per second |
| frantic | 15 min + | full | rapid strobe; hue blends toward red |

Thresholds and brightness levels live in one config module so they can be
tuned (and shortened for testing).

### Multiple sessions

- The board keeps a table keyed by Claude Code `session_id`:
  `{reason, since}` where `since` is when that session started waiting.
- The LED shows the **longest-waiting** session (earliest `since`).
- When ≥2 sessions are waiting, a quick double-blink is inserted every few
  seconds.
- A session entry older than **2 hours** is dropped (closed terminals that
  never sent `SessionEnd`).
- A new waiting event for a session that is already waiting replaces its
  reason but keeps its original `since` (agitation is not reset by Claude
  stacking prompts on an unanswered session). *Exception:* a transition from
  clear → waiting always starts a fresh `since`.

### Idle / connectivity

- No sessions waiting: LED off.
- Wi-Fi disconnected: a faint white blip every few seconds, and the board
  reconnects automatically.

## Architecture

```
Claude Code hook ──HTTP POST──▶ claude-light.local ──▶ session table ──▶ LED
```

### Board (MicroPython) — units

| File | Responsibility | Depends on |
|---|---|---|
| `config.py` | thresholds, colours, brightness, hostname, port | — |
| `secrets.py` | Wi-Fi SSID / password (user-written, git-ignored) | — |
| `sessions.py` | session table: apply event, expire, pick most urgent, count | `config` |
| `animate.py` | pure maths: (reason, seconds waiting, t) → (r, g, b) | `config` |
| `led.py` | thin wrapper over `neopixel` on GPIO48 | hardware |
| `net.py` | Wi-Fi connect / reconnect, hostname (mDNS) | hardware |
| `server.py` | asyncio HTTP server: `POST /event`, `GET /` | `sessions` |
| `main.py` | wires everything: tasks for server, wifi watchdog, render loop (~50 fps) | all |

`sessions.py` and `animate.py` take time as a parameter and import no
hardware modules, so they run under CPython for tests.

### HTTP API

`POST /event` with JSON body:

```json
{"session": "<session_id>", "state": "question|permission|finished|clear|end"}
```

- `question|permission|finished` → mark session waiting with that reason.
- `clear` → session no longer waiting (entry removed).
- `end` → entry removed.
- Responds `204`. Unknown state → `400`.

`GET /` → JSON dump of the session table plus uptime, for debugging.

No authentication: it's a home-LAN toy and the worst an attacker can do is
change an LED colour.

### PC side — hook script

`hooks/claude_light_hook.py` (Python 3 stdlib only):

1. Reads the hook JSON from stdin (`hook_event_name`, `session_id`,
   `tool_name`, `notification_type`).
2. Maps it to a state:

| Hook event | Condition | State |
|---|---|---|
| `PreToolUse` | `tool_name == "AskUserQuestion"` | `question` |
| `Notification` | `notification_type == "permission_prompt"` | `permission` |
| `Stop` | — | `finished` |
| `UserPromptSubmit` | — | `clear` |
| `PostToolUse` | any tool | `clear` |
| `SessionEnd` | — | `end` |
| anything else | — | no request |

3. POSTs to `http://claude-light.local/event` (override with env var
   `CLAUDE_LIGHT_URL`) with a **1 s timeout**.
4. Always exits 0 and prints nothing, so it can never block or alter Claude
   Code.

Registered in the user-level `~/.claude/settings.json` so it covers every
session. Exact hook payload field names will be checked against the current
Claude Code hooks documentation during implementation.

## Error handling

- Board offline / unreachable → hook times out after 1 s, exits 0 silently.
- Malformed request → board returns 400, keeps running.
- Uncaught exception in a board task → logged to serial; `main.py` restarts the
  task. A watchdog timer resets the board if the render loop stalls.
- Board reboots → session table is lost (acceptable; next event repopulates).

## Testing

- **Unit tests (PC, pytest under CPython):** `sessions.py` (ordering, expiry,
  `since` rules, counting) and `animate.py` (stage boundaries, colour blend to
  red, brightness ranges) and the hook's event→state mapping.
- **On-device:** flash MicroPython, upload files, send fake events with `curl`
  using shortened thresholds; user confirms each reason colour and stage.
- **End to end:** real Claude Code session with the hook installed — trigger
  a question, a permission prompt, and a finish; confirm the light and that
  answering clears it.

## Out of scope

- OLED display, sound, buttons (could add later: BOOT button to snooze).
- Authentication / TLS.
- Persisting state across reboots.
- Non-Claude-Code notification sources.
