import asyncio
import network

_wlan = network.WLAN(network.STA_IF)


def connect(ssid, password, hostname):
    network.hostname(hostname)  # also the mDNS name: <hostname>.local
    _wlan.active(True)
    try:
        _wlan.config(pm=_wlan.PM_NONE)  # no power-save: snappier replies
    except Exception:
        pass
    if not _wlan.isconnected():
        _wlan.connect(ssid, password)


def is_up():
    return _wlan.isconnected()


def ip():
    return _wlan.ifconfig()[0] if is_up() else None


async def watchdog(ssid, password, hostname):
    while True:
        await asyncio.sleep(10)
        if not is_up():
            print('wifi down, reconnecting')
            try:
                _wlan.disconnect()
            except Exception:
                pass
            connect(ssid, password, hostname)
