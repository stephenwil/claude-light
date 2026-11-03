import asyncio
import server
from sessions import Sessions

CRLF = b'\r\n'


class Writer:
    def __init__(self):
        self.data = b''
        self.closed = False

    def write(self, b):
        self.data += b

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


def run(raw, eof=True, timeout=1.0):
    async def go():
        r = asyncio.StreamReader()
        r.feed_data(raw)
        if eof:
            r.feed_eof()
        w = Writer()
        s = Sessions()
        await server.handle(r, w, s, lambda: 100, 0, timeout)
        return w, s
    return asyncio.run(go())


def req(body, length=None):
    n = len(body) if length is None else length
    return b'POST /event HTTP/1.0' + CRLF + b'Content-Length: %d' % n + CRLF + CRLF + body


def test_valid_event_204():
    w, s = run(req(b'{"session":"a","state":"question","t":5}'))
    assert w.data.startswith(b'HTTP/1.0 204') and s.count() == 1


def test_oversized_body_rejected():
    w, s = run(req(b'x' * 10, length=5000))
    assert w.data.startswith(b'HTTP/1.0 400') and s.count() == 0


def test_negative_length_rejected():
    w, _ = run(req(b'', length=-1))
    assert w.data.startswith(b'HTTP/1.0 400')


def test_float_t_rejected():
    w, _ = run(req(b'{"session":"a","state":"question","t":1.5}'))
    assert w.data.startswith(b'HTTP/1.0 400')


def test_stalled_client_times_out_and_closes():
    w, _ = run(b'POST /event HTTP/1.0' + CRLF + b'Content-Le', eof=False, timeout=0.2)
    assert w.closed
