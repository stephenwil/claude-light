import asyncio
import json


def _response(code, reason, body=b'', ctype='application/json'):
    head = 'HTTP/1.0 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n' % (
        code, reason, ctype, len(body))
    return head.encode() + body


async def _handle(reader, writer, sessions, clock, started):
    try:
        line = await reader.readline()
        method, path = line.decode().split(' ')[:2]
        length = 0
        while True:
            h = await reader.readline()
            if not h or h == b'\r\n':
                break
            k, _, v = h.decode().partition(':')
            if k.strip().lower() == 'content-length':
                length = int(v.strip())
        if method == 'POST' and path == '/event':
            try:
                data = json.loads(await reader.readexactly(length) if length else b'')
                sessions.apply(data.get('session'), data.get('state'), clock())
                out = _response(204, 'No Content')
            except Exception:
                out = _response(400, 'Bad Request', b'{"error":"bad event"}')
        elif method == 'GET' and path == '/':
            now = clock()
            body = json.dumps({'uptime_s': int(now - started),
                               'sessions': sessions.snapshot(now)}).encode()
            out = _response(200, 'OK', body)
        else:
            out = _response(404, 'Not Found', b'{"error":"not found"}')
        writer.write(out)
        await writer.drain()
    except Exception as e:
        print('http error', e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def serve(sessions, clock, port):
    started = clock()

    async def handler(reader, writer):
        await _handle(reader, writer, sessions, clock, started)

    await asyncio.start_server(handler, '0.0.0.0', port)
    while True:
        await asyncio.sleep(3600)
