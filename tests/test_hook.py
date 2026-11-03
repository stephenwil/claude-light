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
