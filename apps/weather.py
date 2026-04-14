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
# Static body, rays rotate clockwise around it.

SUN_RAYS = [
    [(0, 7), (0, 8)],       # 12 o'clock
    [(1, 11)],              # 1:30
    [(3, 12), (4, 12)],     # 3 o'clock
    [(6, 11)],              # 4:30
    [(7, 7), (7, 8)],       # 6 o'clock
    [(6, 4)],               # 7:30
    [(3, 3), (4, 3)],       # 9 o'clock
    [(1, 4)],               # 10:30
]
RAY_COLORS = ['#ff9900', '#dd6600', '#993300', '#441100',
              '#220800', '#220800', '#441100', '#993300']

def animate_sun(tick):
    frame = ['#111100'] * 128
    Y = '#ffee00'
    for r in range(2, 6):
        for c in range(6, 10):
            px(frame, r, c, Y)
    for c in range(5, 11):
        px(frame, 3, c, Y)
        px(frame, 4, c, Y)
    active = (tick // 2) % 8
    for i, ray_pixels in enumerate(SUN_RAYS):
        dist = min((i - active) % 8, (active - i) % 8)
        for r, c in ray_pixels:
            px(frame, r, c, RAY_COLORS[dist])
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

# ─── Temperature frame ─────────────────────────────────────────────────────

def temp_color(temp_c):
    if temp_c < 0:  return '#0088ff'
    if temp_c < 10: return '#00ccee'
    if temp_c < 21: return '#00ee44'
    if temp_c < 30: return '#ffaa00'
    return '#ff3300'

def make_temp_frame(temp_c):
    frame = ['#000000'] * 128
    color = temp_color(temp_c)
    val = int(round(temp_c))
    chars = (['-'] + list(str(abs(val)))) if val < 0 else list(str(val))
    total_width = len(chars) * 4 - 1
    col_start = (16 - total_width) // 2
    for i, ch in enumerate(chars):
        pixels = DIGITS[ch]
        for r in range(5):
            for c in range(3):
                if pixels[r * 3 + c]:
                    px(frame, 1 + r, col_start + i * 4 + c, color)
    px(frame, 0, 15, color)  # °C dot
    return frame

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
preview_index = WEATHER_TYPES.index(wtype)
print('Weather: {} | {}°C'.format(wtype, round(temp_c) if temp_c else '?'))
print('js-up/down: cycle animations | btn-A: toggle temp | btn-B: refresh')

mode = 'weather'
last_fetch = time()
tick = 0

def on_button_down(button_id):
    global mode, temp_c, code, wtype, preview_index, last_fetch
    if button_id == 'btn-A':
        mode = 'temp' if mode == 'weather' else 'weather'
        print('Mode:', mode)
    elif button_id == 'btn-B':
        print('Refreshing weather...')
        new_temp, new_code = fetch_weather()
        if new_temp is not None:
            temp_c, code = new_temp, new_code
            wtype = weather_type(code)
            preview_index = WEATHER_TYPES.index(wtype)
            last_fetch = time()
            print('Updated: {} | {}°C'.format(wtype, round(temp_c)))
    elif button_id == 'js-up':
        preview_index = (preview_index - 1) % len(WEATHER_TYPES)
        wtype = WEATHER_TYPES[preview_index]
        mode = 'weather'
        print('Preview:', wtype)
    elif button_id == 'js-down':
        preview_index = (preview_index + 1) % len(WEATHER_TYPES)
        wtype = WEATHER_TYPES[preview_index]
        mode = 'weather'
        print('Preview:', wtype)

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

        if mode == 'weather':
            frame = ANIMATIONS[wtype](tick)
        else:
            frame = make_temp_frame(temp_c) if temp_c is not None else ['#000000'] * 128

        pk.stream_frame(frame)
        tick += 1
        sleep(0.1)
except KeyboardInterrupt:
    print('Stopped.')
    pk.stream_frame(['#000000'] * 128)
