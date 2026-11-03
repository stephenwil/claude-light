# Session table: which Claude Code sessions are waiting, why, since when.
# Hardware-free; time is passed in by the caller.
import config

WAITING = ('question', 'permission', 'finished')
STATES = WAITING + ('clear', 'end')


class Sessions:
    def __init__(self):
        self._t = {}  # session_id -> [reason, since]

    def apply(self, session, state, now):
        if not session or not isinstance(session, str):
            raise ValueError('session required')
        if state not in STATES:
            raise ValueError('unknown state')
        if state in WAITING:
            entry = self._t.get(session)
            if entry:
                entry[0] = state  # stacked prompt: keep original since
            else:
                self._t[session] = [state, now]
        else:
            self._t.pop(session, None)

    def expire(self, now):
        for sid in [s for s, (_, since) in self._t.items()
                    if now - since >= config.EXPIRE_S]:
            del self._t[sid]

    def most_urgent(self, now):
        if not self._t:
            return None
        reason, since = min(self._t.values(), key=lambda e: e[1])
        return reason, max(0, now - since)

    def count(self):
        return len(self._t)

    def snapshot(self, now):
        return {sid: {'reason': r, 'waited_s': int(max(0, now - since))}
                for sid, (r, since) in self._t.items()}
