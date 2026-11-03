import machine
import neopixel


class Led:
    def __init__(self, pin):
        self._np = neopixel.NeoPixel(machine.Pin(pin), 1)
        self._last = None

    def show(self, rgb):
        if rgb != self._last:
            self._np[0] = rgb
            self._np.write()
            self._last = rgb
