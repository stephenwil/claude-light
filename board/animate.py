# Pure animation maths: (reason, seconds waiting, time) -> RGB. Hardware-free.
import math

import config

_OFF = (0, 0, 0)


def stage_for(waited_s):
    if waited_s < config.CALM_S:
        return 'calm'
    if waited_s < config.NUDGE_S:
        return 'nudging'
    if waited_s < config.AGITATED_S:
        return 'agitated'
    return 'frantic'


def _blend(a, b, k):
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))


def base_colour(reason, waited_s):
    colour = config.COLOURS[reason]
    over = waited_s - config.AGITATED_S
    if over <= 0:
        return colour
    return _blend(colour, config.RED, min(1.0, over / config.RED_BLEND_S))


def _envelope(stage, t):
    period = config.PERIOD_S[stage]
    phase = (t % period) / period
    if stage == 'frantic':
        return 1.0 if phase < 0.5 else 0.0
    breath = (1 - math.cos(2 * math.pi * phase)) / 2
    if stage == 'agitated':
        return breath ** 4
    return breath


def _scale(colour, k):
    return tuple(max(0, min(255, round(c * k))) for c in colour)


def frame(reason, waited_s, t, waiting_count=1):
    colour = base_colour(reason, waited_s)
    if waiting_count >= 2:
        w = t % config.MULTI_EVERY_S
        if w < 0.4:
            # off / on / off / on in 0.1 s slots
            return colour if int(w / 0.1) % 2 == 1 else _OFF
    stage = stage_for(waited_s)
    return _scale(colour, config.BRIGHTNESS[stage] * _envelope(stage, t))


def offline_frame(t):
    return (8, 8, 8) if t % config.OFFLINE_EVERY_S < 0.1 else _OFF
