import asyncio
import machine
import time

import animate
import config
import net
import server
from led import Led
from sessions import Sessions

try:
    import secrets
except ImportError:
    secrets = None

led = Led(config.LED_PIN)
sessions = Sessions()
_beat = [time.ticks_ms()]


def clock():
    return time.time()


def _stall_check(_t):
    if time.ticks_diff(time.ticks_ms(), _beat[0]) > 10000:
        machine.reset()


async def render():
    period = 1 / config.FPS
    while True:
        _beat[0] = time.ticks_ms()
        t = time.ticks_ms() / 1000
        now = clock()
        sessions.expire(now)
        top = sessions.most_urgent(now)
        if not net.is_up():
            rgb = animate.offline_frame(t)
        elif top:
            rgb = animate.frame(top[0], top[1], t, sessions.count())
        else:
            rgb = (0, 0, 0)
        led.show(rgb)
        await asyncio.sleep(period)


async def forever(name, fn, *args):
    while True:
        try:
            await fn(*args)
        except Exception as e:
            print('task', name, 'crashed:', e)
            await asyncio.sleep(1)


async def run():
    if secrets is None:
        print('no secrets.py - Wi-Fi disabled')
    else:
        net.connect(secrets.SSID, secrets.PASSWORD, config.HOSTNAME)
        asyncio.create_task(forever('wifi', net.watchdog, secrets.SSID, secrets.PASSWORD, config.HOSTNAME))
    asyncio.create_task(forever('http', server.serve, sessions, clock, config.PORT))
    await forever('render', render)


stall = machine.Timer(0)
stall.init(period=2000, mode=machine.Timer.PERIODIC, callback=_stall_check)
try:
    asyncio.run(run())
except KeyboardInterrupt:
    print('stopped')
finally:
    stall.deinit()
    led.show((0, 0, 0))
