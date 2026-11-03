# Claude Light Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An ESP32-S3 WS2812 LED on home Wi-Fi that shows which Claude Code sessions are waiting on the user, why, and (via escalating animation) for how long.

**Architecture:** MicroPython firmware runs an asyncio HTTP server (`POST /event`), a session table, and a ~50 fps render loop. Pure-logic modules (`config`, `animate`, `sessions`) are hardware-free and unit-tested under CPython. A stdlib-only Python hook, registered in user-level Claude Code settings, maps hook events to states and hands the POST to a detached process so Claude Code never waits.

**Tech Stack:** MicroPython (ESP32_GENERIC_S3, SPIRAM_OCT), `neopixel`, `asyncio`, `network`; CPython 3.12 + pytest on the PC; `esptool` + `mpremote` for flashing/upload.

**Spec:** `docs/superpowers/specs/2026-11-03-claude-light-design.md`

## Global Constraints

- LED: WS2812 on GPIO48. Never touch GPIO35/36/37 (PSRAM).
- Board modules `config.py`, `animate.py`, `sessions.py` must not import `machine`, `neopixel`, `network`, or `asyncio`, and must only use syntax MicroPython supports (no dataclasses, no `typing` at runtime, no f-string `=` specifier).
- States: `question` | `permission` | `finished` | `clear` | `end`. Colours: question purple, permission amber, finished blue.
- Stages: calm 0–60 s, nudging 60–300 s, agitated 300–900 s, frantic ≥900 s. Session expiry 7200 s.
- Hostname `claude-light` → `http://claude-light.local`; override URL with `CLAUDE_LIGHT_URL`.
- Hook: stdlib only, exits 0, prints nothing, never waits on the network; off switches `~/.claude/claude-light.off` and `CLAUDE_LIGHT=off`; offline marker `~/.claude/claude-light.offline`, back-off 60 s.
- `board/secrets.py` is git-ignored; never commit or print it.
- Commit messages end with the two attribution lines:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01GDqKim7YhqqseajVCpzntB`.

## Review Focus

1. **Hook stdin that isn't valid JSON or is empty** → hook still exits 0 silently (Task 3 test `test_main_bad_stdin_exits_zero`).
2. **`POST /event` with bad JSON, missing `session`, or unknown `state`** → 400 and server keeps serving (Task 5, curl check).
3. **Clock jumps / `now` earlier than `since`** (board `time.time()` before NTP is unset; use `time.ticks_ms`-based monotonic seconds on the board) → `waited_s` never negative (Task 2 test `test_waited_never_negative`).
4. **Offline marker file corrupt or unreadable** → treated as "not in back-off", hook proceeds (Task 3 test `test_backoff_corrupt_marker`).
5. **Session sends `clear` for an id the board never saw** (board rebooted mid-wait) → no error (Task 2 test `test_clear_unknown_is_noop`).

---

## File Structure

```
board/
  config.py            constants only
  animate.py           pure: stage/colour/brightness maths
  sessions.py          pure: session table
  led.py               neopixel wrapper
  net.py               Wi-Fi connect/reconnect + hostname
  server.py            asyncio HTTP server
  main.py              wiring, tasks, watchdog
  secrets.example.py   template (SSID / PASSWORD)
hooks/
  claude_light_hook.py Claude Code hook + --send background mode
tests/
  conftest.py          puts board/ and hooks/ on sys.path
  test_animate.py
  test_sessions.py
  test_hook.py
pytest.ini
```

---

### Task 1: Config and animation maths

**Files:**
- Create: `board/config.py`, `board/animate.py`, `tests/conftest.py`, `tests/test_animate.py`, `pytest.ini`

**Interfaces:**
- Produces (`config`):
  `CALM_S=60`, `NUDGE_S=300`, `AGITATED_S=900`, `EXPIRE_S=7200`,
  `COLOURS={'question':(160,0,255),'permission':(255,120,0),'finished':(0,70,255)}`, `RED=(255,0,0)`,
  `BRIGHTNESS={'calm':0.06,'nudging':0.2,'agitated':0.55,'frantic':1.0}`,
  `PERIOD_S={'calm':4.0,'nudging':1.5,'agitated':0.5,'frantic':0.1}`,
  `RED_BLEND_S=300` (frantic hue reaches full red 300 s after entering frantic),
  `MULTI_EVERY_S=4.0`, `OFFLINE_EVERY_S=3.0`, `HOSTNAME='claude-light'`, `PORT=80`, `LED_PIN=48`, `FPS=50`.
- Produces (`animate`):
  - `stage_for(waited_s: float) -> str`
  - `base_colour(reason: str, waited_s: float) -> tuple[int,int,int]` — reason colour, blended linearly toward `RED` over `RED_BLEND_S` once frantic.
  - `frame(reason: str, waited_s: float, t: float, waiting_count: int = 1) -> tuple[int,int,int]` — final 0–255 RGB.
  - `offline_frame(t: float) -> tuple[int,int,int]`

- [ ] **Step 1: Write the failing tests** in `tests/test_animate.py` (`conftest.py` inserts `board/` and `hooks/` into `sys.path`; `pytest.ini` sets `testpaths = tests`):

```python
import animate, config

def test_stage_boundaries():
    assert animate.stage_for(0) == 'calm'
    assert animate.stage_for(59.9) == 'calm'
    assert animate.stage_for(60) == 'nudging'
    assert animate.stage_for(300) == 'agitated'
    assert animate.stage_for(900) == 'frantic'

def test_base_colour_not_red_before_frantic():
    assert animate.base_colour('question', 899) == config.COLOURS['question']

def test_base_colour_blends_to_red():
    assert animate.base_colour('finished', 900) == config.COLOURS['finished']
    assert animate.base_colour('finished', 900 + config.RED_BLEND_S) == config.RED
    assert animate.base_colour('finished', 99999) == config.RED

def test_frame_brightness_capped_per_stage():
    peak = max(max(animate.frame('permission', 10, t / 100)) for t in range(400))
    assert 0 < peak <= round(255 * config.BRIGHTNESS['calm']) + 1

def test_frame_frantic_reaches_full():
    peak = max(max(animate.frame('question', 2000, t / 1000)) for t in range(200))
    assert peak >= 250

def test_frame_values_are_ints_in_range():
    for t in range(100):
        c = animate.frame('question', 400, t / 37)
        assert all(isinstance(v, int) and 0 <= v <= 255 for v in c)

def test_multi_blink_inserts_dark_and_bright():
    # during the double-blink window both an off frame and a full-white-ish frame occur
    frames = [animate.frame('finished', 10, config.MULTI_EVERY_S * 3 + i / 100, waiting_count=2) for i in range(40)]
    assert any(max(f) == 0 for f in frames)
    assert any(max(f) >= 250 for f in frames)  # calm alone never gets this bright
    single = [animate.frame('finished', 10, config.MULTI_EVERY_S * 3 + i / 100) for i in range(40)]
    assert all(max(f) < 250 for f in single)

def test_offline_frame_mostly_off():
    frames = [animate.offline_frame(i / 50) for i in range(int(config.OFFLINE_EVERY_S * 50))]
    assert sum(1 for f in frames if max(f) > 0) < len(frames) / 5
```

- [ ] **Step 2: Run** `python -m pytest tests/test_animate.py -v` — Expected: FAIL (`ModuleNotFoundError: animate`).

- [ ] **Step 3: Implement** `board/config.py` with the constants above and `board/animate.py` with the signatures above. Envelope: calm/nudging use a sine "breath" `(1 - cos(2πt/period))/2`; agitated uses a square-ish pulse (sine raised to a power, e.g. `**4`); frantic is a hard on/off strobe at `PERIOD_S['frantic']`. Scale by `BRIGHTNESS[stage]`. Multi-blink: in the first 0.4 s of every `MULTI_EVERY_S` window, if `waiting_count >= 2`, output off/on/off/on in 0.1 s slots (on = current base colour at full brightness). Offline: dim white `(8,8,8)` for the first 0.1 s of every `OFFLINE_EVERY_S`, else off. Use `math` only.

- [ ] **Step 4: Run** `python -m pytest tests/test_animate.py -v` — Expected: all PASS.

- [ ] **Step 5: Commit** `board/ tests/ pytest.ini` — "Add config and animation maths".

---

### Task 2: Session table

**Files:**
- Create: `board/sessions.py`, `tests/test_sessions.py`

**Interfaces:**
- Consumes: `config.EXPIRE_S`
- Produces: `class Sessions` with
  - `apply(session: str, state: str, now: float) -> None` — raises `ValueError` for unknown state or empty session.
  - `expire(now: float) -> None`
  - `most_urgent(now: float) -> tuple[str, float] | None` — `(reason, waited_s)` of earliest `since`.
  - `count() -> int`
  - `snapshot(now: float) -> dict` — `{session_id: {'reason': str, 'waited_s': int}}`

- [ ] **Step 1: Write the failing tests** `tests/test_sessions.py`:

```python
import pytest
from sessions import Sessions

def test_empty():
    s = Sessions(); assert s.most_urgent(0) is None and s.count() == 0

def test_longest_waiting_wins():
    s = Sessions()
    s.apply('a', 'finished', 100); s.apply('b', 'question', 50)
    assert s.most_urgent(200) == ('question', 150) and s.count() == 2

def test_stacked_prompt_keeps_since_but_updates_reason():
    s = Sessions()
    s.apply('a', 'permission', 10); s.apply('a', 'question', 70)
    assert s.most_urgent(100) == ('question', 90)

def test_clear_then_wait_restarts_since():
    s = Sessions()
    s.apply('a', 'finished', 0); s.apply('a', 'clear', 50); s.apply('a', 'finished', 60)
    assert s.most_urgent(70) == ('finished', 10)

def test_end_removes():
    s = Sessions(); s.apply('a', 'question', 0); s.apply('a', 'end', 1)
    assert s.count() == 0

def test_clear_unknown_is_noop():
    s = Sessions(); s.apply('ghost', 'clear', 0); s.apply('ghost', 'end', 0)
    assert s.count() == 0

def test_expiry_after_two_hours():
    s = Sessions(); s.apply('a', 'finished', 0)
    s.expire(7199); assert s.count() == 1
    s.expire(7200); assert s.count() == 0

def test_waited_never_negative():
    s = Sessions(); s.apply('a', 'question', 100)
    assert s.most_urgent(50) == ('question', 0)

@pytest.mark.parametrize('bad', [('', 'question'), ('a', 'bogus')])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        Sessions().apply(bad[0], bad[1], 0)

def test_snapshot():
    s = Sessions(); s.apply('a', 'question', 0)
    assert s.snapshot(12.7) == {'a': {'reason': 'question', 'waited_s': 12}}
```

- [ ] **Step 2: Run** `python -m pytest tests/test_sessions.py -v` — Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `board/sessions.py` as a dict `{id: [reason, since]}`. `waited = max(0, now - since)`.
- [ ] **Step 4: Run** `python -m pytest -v` — Expected: all PASS.
- [ ] **Step 5: Commit** — "Add session table".

---

### Task 3: Claude Code hook

**Files:**
- Create: `hooks/claude_light_hook.py`, `tests/test_hook.py`

**Interfaces:**
- Produces:
  - `map_event(payload: dict) -> str | None`
  - `is_disabled(env: Mapping[str,str], home: Path) -> bool`
  - `in_backoff(home: Path, now: float) -> bool`
  - `send(url: str, body: bytes, home: Path, timeout: float = 1.0) -> None` — POST; on failure write `str(time.time())` to the offline marker; on success delete the marker if present. Never raises.
  - `main(argv: list[str], stdin: TextIO, env: Mapping[str,str], home: Path) -> int` — always returns 0. Normal mode: read stdin JSON, check switches/back-off, map, and spawn `[sys.executable, __file__, '--send', url, json_body]` detached (Windows: `creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`; POSIX: `start_new_session=True`; all std streams `DEVNULL`). `--send` mode: call `send()`.
  - Module constant `DEFAULT_URL = 'http://claude-light.local/event'`.

- [ ] **Step 1: Verify payload field names** against the current Claude Code hooks docs (`claude-code-guide` agent or https://docs.claude.com/en/docs/claude-code/hooks): confirm `hook_event_name`, `session_id`, `tool_name`, and `Notification`'s `notification_type == "permission_prompt"`. If names differ, use the documented ones in the mapping below and note it in the commit message.

- [ ] **Step 2: Write the failing tests** `tests/test_hook.py`:

```python
import io, time, pytest
import claude_light_hook as h

@pytest.mark.parametrize('payload,expected', [
    ({'hook_event_name': 'PreToolUse', 'tool_name': 'AskUserQuestion'}, 'question'),
    ({'hook_event_name': 'PreToolUse', 'tool_name': 'Bash'}, None),
    ({'hook_event_name': 'Notification', 'notification_type': 'permission_prompt'}, 'permission'),
    ({'hook_event_name': 'Notification', 'notification_type': 'idle_prompt'}, None),
    ({'hook_event_name': 'Stop'}, 'finished'),
    ({'hook_event_name': 'UserPromptSubmit'}, 'clear'),
    ({'hook_event_name': 'PostToolUse', 'tool_name': 'Read'}, 'clear'),
    ({'hook_event_name': 'SessionEnd'}, 'end'),
    ({'hook_event_name': 'SessionStart'}, None),
])
def test_map_event(payload, expected):
    assert h.map_event(payload) == expected

def test_off_switch_file(tmp_path):
    (tmp_path / '.claude').mkdir(); (tmp_path / '.claude' / 'claude-light.off').touch()
    assert h.is_disabled({}, tmp_path)

def test_off_switch_env(tmp_path):
    assert h.is_disabled({'CLAUDE_LIGHT': 'off'}, tmp_path)
    assert not h.is_disabled({}, tmp_path)

def test_backoff_window(tmp_path):
    m = tmp_path / '.claude' / 'claude-light.offline'; m.parent.mkdir(); m.write_text('1000')
    assert h.in_backoff(tmp_path, 1059)
    assert not h.in_backoff(tmp_path, 1060)

def test_backoff_corrupt_marker(tmp_path):
    m = tmp_path / '.claude' / 'claude-light.offline'; m.parent.mkdir(); m.write_text('garbage')
    assert not h.in_backoff(tmp_path, 0)

def test_send_failure_writes_marker(tmp_path):
    h.send('http://127.0.0.1:9/event', b'{}', tmp_path, timeout=0.2)
    assert (tmp_path / '.claude' / 'claude-light.offline').exists()

def test_main_bad_stdin_exits_zero(tmp_path, capsys):
    assert h.main([], io.StringIO('not json'), {}, tmp_path) == 0
    assert capsys.readouterr().out == ''

def test_main_is_fast_and_silent(tmp_path, capsys):
    stdin = io.StringIO('{"hook_event_name":"Stop","session_id":"s1"}')
    t0 = time.perf_counter()
    assert h.main([], stdin, {'CLAUDE_LIGHT_URL': 'http://10.255.255.1/event'}, tmp_path) == 0
    assert time.perf_counter() - t0 < 0.5
    assert capsys.readouterr().out == ''
```

- [ ] **Step 3: Run** `python -m pytest tests/test_hook.py -v` — Expected: FAIL (module missing).
- [ ] **Step 4: Implement** `hooks/claude_light_hook.py` per the Interfaces block, using `urllib.request` only. Wrap all of `main` in `try/except Exception: pass`. Body sent: `{"session": session_id, "state": state}`. Entry point: `if __name__ == '__main__': sys.exit(main(sys.argv[1:], sys.stdin, os.environ, Path.home()))`.
- [ ] **Step 5: Run** `python -m pytest -v` — Expected: all PASS.
- [ ] **Step 6: Latency check** — with nothing listening: `echo {"hook_event_name":"Stop","session_id":"x"} | python hooks/claude_light_hook.py` timed with `Measure-Command` in PowerShell. Expected: < 100 ms beyond Python start-up (record the number).
- [ ] **Step 7: Commit** — "Add Claude Code hook with off switches and offline back-off".

---

### Task 4: Flash MicroPython

**Files:** none in repo (firmware download goes in the session scratchpad, its own empty directory).

- [ ] **Step 1:** Ask the user to plug the board into the PC on the native USB port (rear port preferred); find its COM port (`Get-PnpDevice -PresentOnly -Class Ports`, look for VID 303A).
- [ ] **Step 2:** Download the latest stable `ESP32_GENERIC_S3-SPIRAM_OCT-*.bin` from https://micropython.org/download/ESP32_GENERIC_S3/ into a new empty scratch directory.
- [ ] **Step 3:** `python -m esptool --chip esp32s3 --port COMx erase-flash`, then `python -m esptool --chip esp32s3 --port COMx write-flash -z 0 <file>.bin`. Expected: "Hash of data verified."
- [ ] **Step 4:** `pip install mpremote`; `mpremote connect COMx exec "import esp32, gc; print(gc.mem_free())"`. Expected: a number > 8,000,000 (PSRAM visible).
- [ ] **Step 5:** `mpremote connect COMx exec "import neopixel, machine; n=neopixel.NeoPixel(machine.Pin(48),1); n[0]=(0,0,40); n.write()"` — user confirms LED is dim blue.

---

### Task 5: Board runtime (LED, Wi-Fi, server, main)

**Files:**
- Create: `board/led.py`, `board/net.py`, `board/server.py`, `board/main.py`, `board/secrets.example.py`

**Interfaces:**
- Consumes: `config.*`, `animate.frame`, `animate.offline_frame`, `Sessions`
- Produces:
  - `led.Led(pin: int)` with `.show(rgb: tuple) -> None`
  - `net.connect(ssid, password, hostname) -> None` (non-blocking start); `net.is_up() -> bool`; `async net.watchdog(ssid, password, hostname)` — reconnects every 10 s while down.
  - `async server.serve(sessions: Sessions, clock: callable, port: int)` — handles `POST /event` (204 / 400) and `GET /` (200 JSON: `{"uptime_s": int, "sessions": snapshot}`).
  - `main.py`: `clock()` = `time.ticks_ms()/1000` relative to boot; tasks: server, wifi watchdog, render loop at `config.FPS` that calls `sessions.expire`, picks `most_urgent`, shows `frame(...)` or `offline_frame` when Wi-Fi is down, or off; feeds `machine.WDT(timeout=8000)` each frame. Each task wrapped in a loop that logs and restarts on exception.
  - `secrets.example.py`: `SSID = "your-wifi"`, `PASSWORD = "your-password"`.

- [ ] **Step 1:** Implement the five files. HTTP parsing: read request line + headers until blank line, read `Content-Length` bytes, `json.loads`; any exception → 400. Hostname: `network.hostname(config.HOSTNAME)` before `WLAN.active(True)`.
- [ ] **Step 2:** Ask the user to create `board/secrets.py` from the example with their Wi-Fi details (do not read it back). Confirm it's ignored: `git check-ignore board/secrets.py` → prints the path.
- [ ] **Step 3:** Upload: `mpremote connect COMx cp board/*.py :` then `mpremote connect COMx reset`. Move the board to the USB charger.
- [ ] **Step 4:** `curl http://claude-light.local/` — Expected: `{"uptime_s": …, "sessions": {}}`. If `.local` doesn't resolve on Windows, find the IP in the router or via `mpremote exec "import network; print(network.WLAN().ifconfig())"` and note it for `CLAUDE_LIGHT_URL`.
- [ ] **Step 5:** Bad input: `curl -i -X POST http://claude-light.local/event -d "nope"` → `400`; then `curl http://claude-light.local/` still answers.
- [ ] **Step 6:** Commit `board/` (not `secrets.py`) — "Add board runtime: LED, Wi-Fi, HTTP server, main loop".

---

### Task 6: On-device visual check

- [ ] **Step 1:** Temporarily upload a `config.py` with `CALM_S=5, NUDGE_S=15, AGITATED_S=30, RED_BLEND_S=15` (do not commit).
- [ ] **Step 2:** For each reason, `curl -X POST http://claude-light.local/event -d '{"session":"t1","state":"<reason>"}'`; user confirms colour and that it escalates calm → nudging → agitated → frantic → red. Then send `clear`; LED goes off.
- [ ] **Step 3:** Two sessions (`t1`, `t2`) waiting → user confirms double-blink.
- [ ] **Step 4:** Re-upload the real `board/config.py`; `git status` shows clean.

---

### Task 7: Install hooks and end-to-end test

**Files:**
- Modify: `~/.claude/settings.json` (user-level; read it first, merge — don't overwrite existing hooks)
- Create: `README.md` (what it is, wiring, setup steps, off switches)

- [ ] **Step 1:** Add command hooks for `PreToolUse` (matcher `AskUserQuestion`), `Notification`, `Stop`, `UserPromptSubmit`, `PostToolUse` (matcher `*`), `SessionEnd`, each running `python C:/Users/steph/repos/claude-light/hooks/claude_light_hook.py` (set `CLAUDE_LIGHT_URL` in the command only if `.local` didn't resolve in Task 5). Show the user the diff before saving.
- [ ] **Step 2:** In a new Claude Code session: ask it a question that triggers `AskUserQuestion` → purple; answer → off. Trigger a permission prompt → amber; approve → off. Let it finish → blue; send a message → off.
- [ ] **Step 3:** Unplug the board; run a few tool calls; confirm no noticeable slowdown and `~/.claude/claude-light.offline` appears. Plug back in; within ~60 s the light works again.
- [ ] **Step 4:** `touch ~/.claude/claude-light.off` → light no longer reacts; delete → reacts again.
- [ ] **Step 5:** Write `README.md`; commit; `git push`.
