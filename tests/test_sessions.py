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

def test_stale_event_ignored_after_end():
    # end (fired later) arrives before finished (fired earlier): finished must be dropped
    s = Sessions()
    s.apply('a', 'end', 10, seq=2.0)
    s.apply('a', 'finished', 11, seq=1.0)
    assert s.count() == 0

def test_stale_waiting_does_not_override_newer_reason():
    s = Sessions()
    s.apply('a', 'question', 10, seq=5.0)
    s.apply('a', 'permission', 11, seq=4.0)
    assert s.most_urgent(12) == ('question', 2)

def test_events_without_seq_always_apply():
    s = Sessions()
    s.apply('a', 'end', 10, seq=2.0)
    s.apply('a', 'finished', 11)
    assert s.count() == 1

def test_seq_memory_expires():
    s = Sessions()
    s.apply('a', 'end', 0, seq=2.0)
    s.expire(7200)
    s.apply('a', 'finished', 7201, seq=1.0)
    assert s.count() == 1
