# Tunable constants for Claude Light. Hardware-free; imported by tests too.

# Agitation stage thresholds (seconds waiting)
CALM_S = 60
NUDGE_S = 300
AGITATED_S = 900

# Drop a waiting session after this long (closed terminal, no SessionEnd)
EXPIRE_S = 7200

# Base colour per reason
COLOURS = {
    'question': (160, 0, 255),    # purple
    'permission': (255, 120, 0),  # amber
    'finished': (0, 70, 255),     # blue
}
RED = (255, 0, 0)

# Peak brightness (0..1) and animation period per stage
BRIGHTNESS = {'calm': 0.06, 'nudging': 0.2, 'agitated': 0.55, 'frantic': 1.0}
PERIOD_S = {'calm': 4.0, 'nudging': 1.5, 'agitated': 0.5, 'frantic': 0.1}

# Frantic hue reaches full red this long after entering frantic
RED_BLEND_S = 300

# Double-blink when >=2 sessions wait, every N seconds
MULTI_EVERY_S = 4.0
# Faint white blip while Wi-Fi is down, every N seconds
OFFLINE_EVERY_S = 3.0

HOSTNAME = 'claude-light'
PORT = 80
LED_PIN = 48
FPS = 50
