import sys
import urllib.request
import json
from time import sleep, time

from communitysdk import list_connected_devices, RetailPixelKitSerial as PixelKit

# Montreal
LAT = 45.5017
LON = -73.5673
REFRESH_INTERVAL = 600

WEATHER_TYPES = ['sun', 'cloudy', 'rain', 'snow', 'fog']

DIGITS = {
    '0': [1,1,1, 1,0,1, 1,0,1, 1,0,1, 1,1,1],
    '1': [0,1,0, 1,1,0, 0,1,0, 0,1,0, 1,1,1],
    '2': [1,1,1, 0,0,1, 1,1,1, 1,0,0, 1,1,1],
    '3': [1,1,1, 0,0,1, 0,1,1, 0,0,1, 1,1,1],
    '4': [1,0,1, 1,0,1, 1,1,1, 0,0,1, 0,0,1],
    '5': [1,1,1, 1,0,0, 1,1,1, 0,0,1, 1,1,1],
    '6': [1,1,1, 1,0,0, 1,1,1, 1,0,1, 1,1,1],
    '7': [1,1,1, 0,0,1, 0,1,0, 0,1,0, 0,1,0],
    '8': [1,1,1, 1,0,1, 1,1,1, 1,0,1, 1,1,1],
    '9': [1,1,1, 1,0,1, 1,1,1, 0,0,1, 1,1,1],
    '-': [0,0,0, 0,0,0, 1,1,1, 0,0,0, 0,0,0],
}

def px(frame, row, col, color):
    if 0 <= row < 8 and 0 <= col < 16:
        frame[row * 16 + col] = color

# ─── Sun ───────────────────────────────────────────────────────────────────
# Dots shoot out from the sun body in 8 directions and fade as they travel.
# Each stream is a list of (row, col) pixels ordered outward from the body.

SUN_STREAMS = [
    [(1, 7),  (0, 7)],           # up
    [(1, 10), (0, 11)],          # up-right
    [(3, 11), (3, 12), (3, 13)], # right
    [(6, 10), (7, 11)],          # down-right
    [(6, 7),  (7, 7)],           # down
    [(6, 5),  (7, 4)],           # down-left
    [(3, 4),  (3, 3),  (3, 2)],  # left
    [(1, 5),  (0, 4)],           # up-left
]

# Dot colors: leading (just left body) → fading to black
RAY_DOT  = ['#ffcc00', '#ff8800', '#cc4400', '#551100']
RAY_GAP  = 5   # blank frames between pulses
RAY_STEP = 2   # ticks per position advance (controls speed)

def animate_sun(tick):
    frame = ['#111100'] * 128
    Y = '#ffee00'
    # Sun body
    for r in range(2, 6):
        for c in range(6, 10):
            px(frame, r, c, Y)
    for c in range(5, 11):
        px(frame, 3, c, Y)
        px(frame, 4, c, Y)

    # Animate each stream: a dot travels outward and fades
    max_len = max(len(s) for s in SUN_STREAMS)
    period = max_len + RAY_GAP   # total cycle length per stream
    pulse = (tick // RAY_STEP) % period  # current position of leading dot

    for stream in SUN_STREAMS:
        for j, (r, c) in enumerate(stream):
            # age = how many steps behind the leading dot this pixel is
            age = pulse - j
            if 0 <= age < len(RAY_DOT):
                px(frame, r, c, RAY_DOT[age])
    return frame

# ─── Clouds ────────────────────────────────────────────────────────────────
# Two clouds at different heights scrolling left at different speeds.

# Big cloud: two bumps, ~11px wide
CLOUD_A = [
    (-2, 1), (-2, 2), (-2, 3),
    (-2, 6), (-2, 7),
    (-1, 0), (-1, 1), (-1, 2), (-1, 3), (-1, 4), (-1, 5), (-1, 6), (-1, 7), (-1, 8),
    ( 0,-1), ( 0, 0), ( 0, 1), ( 0, 2), ( 0, 3), ( 0, 4), ( 0, 5), ( 0, 6), ( 0, 7), ( 0, 8), ( 0, 9),
    ( 1,-1), ( 1, 0), ( 1, 1), ( 1, 2), ( 1, 3), ( 1, 4), ( 1, 5), ( 1, 6), ( 1, 7), ( 1, 8), ( 1, 9),
    ( 2, 0), ( 2, 1), ( 2, 2), ( 2, 3), ( 2, 4), ( 2, 5), ( 2, 6), ( 2, 7), ( 2, 8),
]

# Small cloud: one bump, ~6px wide
CLOUD_B = [
    (-1, 1), (-1, 2), (-1, 3), (-1, 4),
    ( 0, 0), ( 0, 1), ( 0, 2), ( 0, 3), ( 0, 4), ( 0, 5),
    ( 1, 0), ( 1, 1), ( 1, 2), ( 1, 3), ( 1, 4), ( 1, 5),
    ( 2, 1), ( 2, 2), ( 2, 3), ( 2, 4),
]

CLOUD_A_MAX = max(dr for dr, _ in CLOUD_A)
CLOUD_B_MAX = max(dr for dr, _ in CLOUD_B)

def draw_cloud(frame, row, col, shape, max_dr, body, shadow):
    for dr, dc in shape:
        r, c = row + dr, col + dc
        if 0 <= r < 8 and 0 <= c < 16:
            frame[r * 16 + c] = shadow if dr == max_dr else body

def animate_cloudy(tick):
    frame = ['#112233'] * 128
    # Cloud A: enters from right, ~27px travel span, 1px per 3 ticks
    xa = 16 - (tick // 3) % 28
    draw_cloud(frame, 2, xa, CLOUD_A, CLOUD_A_MAX, '#e0e0e0', '#aaaaaa')
    # Cloud B: slower, offset start so screen isn't empty
    xb = 16 - (tick // 4 + 12) % 23
    draw_cloud(frame, 5, xb, CLOUD_B, CLOUD_B_MAX, '#bbbbbb', '#777777')
    return frame

# ─── Rain ──────────────────────────────────────────────────────────────────
# Storm cloud covers top 3 rows. Diagonal drops fall below it.

RAIN_DROPS = [
    # (base_col, init_step, ticks_per_step)
    ( 0, 0, 3), ( 2, 3, 4), ( 4, 1, 3), ( 6, 4, 4),
    ( 8, 2, 3), (10, 5, 4), (12, 0, 3), (14, 3, 4),
    ( 1, 6, 5), ( 5, 2, 4), ( 9, 4, 3), (13, 1, 4),
]

def animate_rain(tick):
    frame = ['#001133'] * 128
    for c in range(16): px(frame, 0, c, '#445566')
    for c in range(16): px(frame, 1, c, '#556677')
    for c in range(16): px(frame, 2, c, '#778899')
    for base_col, init_step, period in RAIN_DROPS:
        step = (init_step + tick // period) % 7  # 5 visible rows + 2-row gap
        row = 3 + step
        if row > 7:
            continue
        col = (base_col + step) % 16
        px(frame, row, col, '#aaccff')           # bright tip
        if row > 3 and col > 0:                  # trail (no edge wrap)
            px(frame, row - 1, col - 1, '#3366ff')
    return frame

# ─── Snow ──────────────────────────────────────────────────────────────────
# Snowflakes falling at different speeds on a dark blue sky, no cloud.

SNOW_FLAKES = [
    # (col, init_row, ticks_per_step)
    ( 0, 0, 4), ( 2, 3, 5), ( 5, 1, 4), ( 7, 5, 6),
    ( 9, 2, 4), (11, 0, 5), (13, 4, 4), (15, 2, 6),
    ( 3, 6, 5), ( 8, 3, 4), (12, 1, 5), ( 6, 7, 6),
]

def animate_snow(tick):
    frame = ['#000820'] * 128
    W = '#ffffff'
    A = '#6688cc'
    for col, init_row, period in SNOW_FLAKES:
        row = (init_row + tick // period) % 8
        px(frame, row, col, W)
        if row > 0: px(frame, row - 1, col, A)
        if row < 7: px(frame, row + 1, col, A)
        if col > 0: px(frame, row, col - 1, A)
        if col < 15: px(frame, row, col + 1, A)
    return frame

# ─── Fog ───────────────────────────────────────────────────────────────────
# Horizontal bands drifting left/right at different speeds.

FOG_BANDS = [
    # (row, length, color, direction, speed_divisor)
    (0, 12, '#444444',  1, 8),
    (1, 14, '#777777', -1, 6),
    (2, 10, '#555555',  1, 9),
    (3, 13, '#888888', -1, 7),
    (4, 11, '#666666',  1, 8),
    (5, 15, '#999999', -1, 5),
    (6,  9, '#555555',  1, 10),
    (7, 13, '#777777', -1, 6),
]

def animate_fog(tick):
    frame = ['#111111'] * 128
    for row, length, color, direction, div in FOG_BANDS:
        offset = (direction * tick // div) % 16
        for i in range(length):
            px(frame, row, (offset + i) % 16, color)
    return frame

ANIMATIONS = {
    'sun':    animate_sun,
    'cloudy': animate_cloudy,
    'rain':   animate_rain,
    'snow':   animate_snow,
    'fog':    animate_fog,
}

# ─── Temperature overlay ───────────────────────────────────────────────────
# Draws temp digits directly on top of an existing animation frame.
# Only "on" pixels are painted (white), so the animation shows through.

def overlay_temp(frame, temp_c):
    val = int(round(temp_c))
    chars = (['-'] + list(str(abs(val)))) if val < 0 else list(str(val))
    total_width = len(chars) * 4 - 1
    col_start = 15 - total_width   # right-aligned
    row_start = 3                  # bottom half of display

    # Collect lit pixel positions
    lit = set()
    for i, ch in enumerate(chars):
        pixels = DIGITS[ch]
        for r in range(5):
            for c in range(3):
                if pixels[r * 3 + c]:
                    lit.add((row_start + r, col_start + i * 4 + c))
    lit.add((row_start, col_start + total_width + 1))  # ° dot

    # Dark outline around each lit pixel so text reads on any background
    for r, c in lit:
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (nr, nc) not in lit:
                px(frame, nr, nc, '#000000')

    # White digits on top
    for r, c in lit:
        px(frame, r, c, '#ffffff')

# ─── Weather fetch ─────────────────────────────────────────────────────────

def fetch_weather():
    url = (
        'https://api.open-meteo.com/v1/forecast'
        '?latitude={}&longitude={}'
        '&current=temperature_2m,weathercode'
        '&temperature_unit=celsius'
    ).format(LAT, LON)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        c = data['current']
        return float(c['temperature_2m']), int(c['weathercode'])
    except Exception as e:
        print('Weather fetch error:', e)
        return None, None

def weather_type(code):
    if code == 0:                                                    return 'sun'
    if code in [1, 2, 3]:                                           return 'cloudy'
    if code in [45, 48]:                                            return 'fog'
    if code in [51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99]: return 'rain'
    if code in [71, 73, 75, 77, 85, 86]:                           return 'snow'
    return 'cloudy'

# ─── Connect ───────────────────────────────────────────────────────────────

devices = list_connected_devices()
pk = next(filter(lambda d: isinstance(d, PixelKit), devices), None)

if pk is None:
    print('No Pixel Kit found :(')
    sys.exit()

print('Connected! Fetching Montreal weather...')
temp_c, code = fetch_weather()
wtype = weather_type(code) if code is not None else 'cloudy'
print('Weather: {} | {}°C'.format(wtype, round(temp_c) if temp_c else '?'))
print('btn-B: show current weather illustration')

last_fetch = time()
tick = 0
anim_start = 0  # tick when current animation started (resets on switch)

def on_button_down(button_id):
    global temp_c, code, wtype, preview_index, last_fetch, anim_start
    if button_id == 'btn-B':
        new_temp, new_code = fetch_weather()
        if new_temp is not None:
            temp_c, code = new_temp, new_code
            last_fetch = time()
        wtype = weather_type(code) if code is not None else 'cloudy'
        preview_index = WEATHER_TYPES.index(wtype)
        anim_start = tick
        print('Weather: {} | {}°C'.format(wtype, round(temp_c) if temp_c else '?'))

pk.on_button_down = on_button_down

try:
    while True:
        if time() - last_fetch > REFRESH_INTERVAL:
            new_temp, new_code = fetch_weather()
            if new_temp is not None:
                temp_c, code = new_temp, new_code
                wtype = weather_type(code)
                preview_index = WEATHER_TYPES.index(wtype)
                print('Auto-refresh: {} | {}°C'.format(wtype, round(temp_c)))
            last_fetch = time()

        frame = ANIMATIONS[wtype](tick - anim_start)
        if temp_c is not None:
            overlay_temp(frame, temp_c)

        pk.stream_frame(frame)
        tick += 1
        sleep(0.1)
except KeyboardInterrupt:
    print('Stopped.')
    pk.stream_frame(['#000000'] * 128)
