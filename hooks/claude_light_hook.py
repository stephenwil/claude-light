"""Claude Code hook for Claude Light.

Reads the hook JSON on stdin, maps it to a board state, and hands the HTTP
POST to a detached background process so Claude Code never waits on the
network. Always exits 0 and prints nothing.

Off switches: ~/.claude/claude-light.off, or CLAUDE_LIGHT=off.
Offline back-off: ~/.claude/claude-light.offline (skip sends for 60 s).
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_URL = 'http://claude-light.local/event'
BACKOFF_S = 60


def _claude_dir(home):
    return Path(home) / '.claude'


def _marker(home):
    return _claude_dir(home) / 'claude-light.offline'


def map_event(payload):
    event = payload.get('hook_event_name')
    if event == 'PreToolUse':
        return 'question' if payload.get('tool_name') == 'AskUserQuestion' else None
    if event == 'Notification':
        return 'permission' if payload.get('notification_type') == 'permission_prompt' else None
    return {
        'Stop': 'finished',
        'UserPromptSubmit': 'clear',
        'PostToolUse': 'clear',
        'SessionEnd': 'end',
    }.get(event)


def is_disabled(env, home):
    if str(env.get('CLAUDE_LIGHT', '')).lower() == 'off':
        return True
    return (_claude_dir(home) / 'claude-light.off').exists()


def in_backoff(home, now):
    try:
        since = float(_marker(home).read_text().strip())
    except (OSError, ValueError):
        return False
    return 0 <= now - since < BACKOFF_S


def send(url, body, home, timeout=1.0):
    marker = _marker(home)
    try:
        req = urllib.request.Request(
            url, data=body, method='POST',
            headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=timeout).close()
    except Exception:
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(str(time.time()))
        except OSError:
            pass
        return
    try:
        marker.unlink()
    except OSError:
        pass


def _spawn(url, body, home):
    args = [sys.executable, os.path.abspath(__file__), '--send', url, body, str(home)]
    kwargs = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL, close_fds=True)
    if os.name == 'nt':
        kwargs['creationflags'] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP
                                   | subprocess.CREATE_NO_WINDOW)
    else:
        kwargs['start_new_session'] = True
    subprocess.Popen(args, **kwargs)


def main(argv, stdin, env, home):
    try:
        if argv[:1] == ['--send'] and len(argv) >= 4:
            send(argv[1], argv[2].encode(), Path(argv[3]))
            return 0
        if is_disabled(env, home) or in_backoff(home, time.time()):
            return 0
        payload = json.loads(stdin.read() or '{}')
        state = map_event(payload)
        session = payload.get('session_id')
        if not state or not session:
            return 0
        body = json.dumps({'session': session, 'state': state})
        _spawn(env.get('CLAUDE_LIGHT_URL') or DEFAULT_URL, body, home)
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:], sys.stdin, os.environ, Path.home()))
