# main.py – Kano Pixel Kit standalone launcher (MicroPython / Pixel32)
#
# Dial:      0–1365  → Pomodoro
#            1366–2730 → Weather
#            2731–4095 → Sound Visualizer
#
# Pomodoro:  btn-A start/pause | btn-B reset | js-up/down change duration
# Weather:   btn-B refresh
# Sound:     live mic volume bar

import PixelKit as pk
import utime
import network
import urequests
import json
from machine import ADC, Pin

# ── Pixel helpers ──────────────────────────────────────────────────

B = (0, 0, 0)

def px(f, row, col, color):
    if 0 <= row < 8 and 0 <= col < 16:
        f[row * 16 + col] = color

def show(f):
    for i, c in enumerate(f):
        pk.set_pixel(i % 16, i // 16, c)
    pk.render()

# ── App selector ──────────────────────────────────────────────────

APP = 0  # 0=pomodoro  1=weather  2=sound

def _on_dial(v):
    global APP
    APP = 0 if v < 1365 else (1 if v < 2730 else 2)

pk.on_dial = _on_dial

# ── WiFi ──────────────────────────────────────────────────────────

wifi_ok = False

def connect_wifi():
    global wifi_ok
    sta = network.WLAN(network.STA_IF)
    if sta.isconnected():
        wifi_ok = True
        return
    sta.active(True)
    sta.connect('Manoir', 'monsieurferland2015')
    for _ in range(40):
        if sta.isconnected():
            wifi_ok = True
            return
        utime.sleep(0.5)

# ── Digit bitmaps (shared by Pomodoro + Weather) ──────────────────

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

# ══════════════════════════════════════════════════════════════════
# POMODORO
# ══════════════════════════════════════════════════════════════════

pom_min    = 15
pom_total  = pom_min * 60
pom_left   = pom_total
pom_run    = False
pom_last   = 0

def pom_color():
    if not pom_run: return (255, 136, 0)
    r = pom_left / pom_total
    if r > 0.5:  return (0, 255, 0)
    if r > 0.25: return (255, 255, 0)
    return (255, 0, 0)

def pom_digit(f, d, x0, c):
    pix = DIGITS[d]
    for row in range(5):
        for col in range(3):
            if pix[row * 3 + col]:
                f[(row + 1) * 16 + x0 + col] = c

def pom_frame():
    f = [B] * 128
    c = pom_color()
    m, s = pom_left // 60, pom_left % 60
    pom_digit(f, str(m // 10), 0, c)
    pom_digit(f, str(m % 10), 4, c)
    f[2 * 16 + 7] = c
    f[4 * 16 + 7] = c
    pom_digit(f, str(s // 10), 8, c)
    pom_digit(f, str(s % 10), 12, c)
    prog = int((pom_left / pom_total) * 16)
    for i in range(prog):
        f[7 * 16 + i] = c
    return f

def pom_tick():
    global pom_left, pom_run, pom_last
    if pom_run:
        now = utime.time()
        elapsed = now - pom_last
        if elapsed >= 1:
            pom_left -= int(elapsed)
            pom_last = now
            if pom_left <= 0:
                pom_left = 0
                pom_run = False
                pom_done()

def pom_done():
    for _ in range(6):
        pk.set_background((255, 255, 255)); pk.render(); utime.sleep(0.2)
        pk.clear();                         pk.render(); utime.sleep(0.2)

def pom_change(d):
    global pom_min, pom_total, pom_left
    step = 1 if pom_min < 10 else 5
    pom_min   = max(1, min(60, pom_min + d * step))
    pom_total = pom_min * 60
    pom_left  = pom_total

# ══════════════════════════════════════════════════════════════════
# WEATHER
# ══════════════════════════════════════════════════════════════════

LAT = 45.5017
LON = -73.5673
REFRESH = 600

w_temp      = None
w_code      = None
w_is_day    = 1
w_type      = 'cloudy'
w_refresh   = False
w_last      = 0
w_tick      = 0
w_anim_start = 0

# Sun
SUN_STREAMS = [
    [(1,7),(0,7)], [(1,10),(0,11)], [(3,11),(3,12),(3,13)], [(6,10),(7,11)],
    [(6,7),(7,7)], [(6,5),(7,4)],  [(3,4),(3,3),(3,2)],    [(1,5),(0,4)],
]
RAY = [(255,204,0),(255,136,0),(204,68,0),(85,17,0)]
RAY_GAP = 5; RAY_STEP = 2

def anim_sun(tick):
    f = [(17,17,0)] * 128
    Y = (255,238,0)
    for r in range(2,6):
        for c in range(6,10): px(f,r,c,Y)
    for c in range(5,11): px(f,3,c,Y); px(f,4,c,Y)
    period = max(len(s) for s in SUN_STREAMS) + RAY_GAP
    pulse  = (tick // RAY_STEP) % period
    for stream in SUN_STREAMS:
        for j,(r,c) in enumerate(stream):
            age = pulse - j
            if 0 <= age < len(RAY): px(f,r,c,RAY[age])
    return f

# Moon
MOON_PX = [(1,6),(1,7),(2,5),(2,6),(2,7),(3,4),(3,5),(3,6),
            (4,4),(4,5),(4,6),(5,5),(5,6),(5,7),(6,6),(6,7)]
STAR_PX = [(0,10),(0,13),(1,12),(2,15),(3,11),(4,14),(5,12),
            (6,10),(7,13),(7,9),(0,3),(6,2)]

def anim_moon(tick):
    f = [(0,0,16)] * 128
    M = (255,238,136)
    for r,c in MOON_PX: px(f,r,c,M)
    for i,(r,c) in enumerate(STAR_PX):
        phase = (tick + i*7) % 24
        if phase < 18: px(f,r,c,(255,255,255) if phase < 12 else (102,102,102))
    return f

# Clouds
CLOUD_A = [(-2,1),(-2,2),(-2,3),(-2,6),(-2,7),(-1,0),(-1,1),(-1,2),(-1,3),(-1,4),
           (-1,5),(-1,6),(-1,7),(-1,8),(0,-1),(0,0),(0,1),(0,2),(0,3),(0,4),(0,5),
           (0,6),(0,7),(0,8),(0,9),(1,-1),(1,0),(1,1),(1,2),(1,3),(1,4),(1,5),
           (1,6),(1,7),(1,8),(1,9),(2,0),(2,1),(2,2),(2,3),(2,4),(2,5),(2,6),(2,7),(2,8)]
CLOUD_B = [(-1,1),(-1,2),(-1,3),(-1,4),(0,0),(0,1),(0,2),(0,3),(0,4),(0,5),
           (1,0),(1,1),(1,2),(1,3),(1,4),(1,5),(2,1),(2,2),(2,3),(2,4)]
CA_MAX = max(dr for dr,_ in CLOUD_A)
CB_MAX = max(dr for dr,_ in CLOUD_B)

def draw_cloud(f,row,col,shape,max_dr,body,shadow):
    for dr,dc in shape:
        r,c = row+dr, col+dc
        if 0<=r<8 and 0<=c<16:
            f[r*16+c] = shadow if dr==max_dr else body

def anim_cloudy(tick):
    f = [(17,34,51)] * 128
    xa = 16-(tick//3)%28
    draw_cloud(f,2,xa,CLOUD_A,CA_MAX,(224,224,224),(170,170,170))
    xb = 16-(tick//4+12)%23
    draw_cloud(f,5,xb,CLOUD_B,CB_MAX,(187,187,187),(119,119,119))
    return f

# Rain
RAIN_DROPS = [(0,0,3),(2,3,4),(4,1,3),(6,4,4),(8,2,3),(10,5,4),
              (12,0,3),(14,3,4),(1,6,5),(5,2,4),(9,4,3),(13,1,4)]

def anim_rain(tick):
    f = [(0,17,51)] * 128
    for c in range(16):
        px(f,0,c,(68,85,102)); px(f,1,c,(85,102,119)); px(f,2,c,(119,136,153))
    for base_col,init_step,period in RAIN_DROPS:
        step = (init_step+tick//period)%7; row = 3+step
        if row > 7: continue
        col = (base_col+step)%16
        px(f,row,col,(170,204,255))
        if row>3 and col>0: px(f,row-1,col-1,(51,102,255))
    return f

# Snow
SNOW_FLAKES = [(0,0,4),(2,3,5),(5,1,4),(7,5,6),(9,2,4),(11,0,5),
               (13,4,4),(15,2,6),(3,6,5),(8,3,4),(12,1,5),(6,7,6)]

def anim_snow(tick):
    f = [(0,8,32)] * 128
    for col,init_row,period in SNOW_FLAKES:
        row = (init_row+tick//period)%8
        px(f,row,col,(255,255,255))
        if row>0: px(f,row-1,col,(102,136,204))
        if row<7: px(f,row+1,col,(102,136,204))
        if col>0: px(f,row,col-1,(102,136,204))
        if col<15: px(f,row,col+1,(102,136,204))
    return f

# Fog
FOG_BANDS = [
    (0,12,(68,68,68),1,8),(1,14,(119,119,119),-1,6),(2,10,(85,85,85),1,9),
    (3,13,(136,136,136),-1,7),(4,11,(102,102,102),1,8),(5,15,(153,153,153),-1,5),
    (6,9,(85,85,85),1,10),(7,13,(119,119,119),-1,6),
]

def anim_fog(tick):
    f = [(17,17,17)] * 128
    for row,length,color,direction,div in FOG_BANDS:
        offset = (direction*tick//div)%16
        for i in range(length): px(f,row,(offset+i)%16,color)
    return f

ANIMS = {'sun':anim_sun,'moon':anim_moon,'cloudy':anim_cloudy,
         'rain':anim_rain,'snow':anim_snow,'fog':anim_fog}

def code_to_type(code, is_day):
    if code == 0:                                                      return 'sun' if is_day else 'moon'
    if code in [1,2,3]:                                                return 'cloudy'
    if code in [45,48]:                                                return 'fog'
    if code in [51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99]:    return 'rain'
    if code in [71,73,75,77,85,86]:                                    return 'snow'
    return 'cloudy'

def overlay_temp(f, temp_c):
    val = int(round(temp_c))
    chars = (['-'] + list(str(abs(val)))) if val < 0 else list(str(val))
    total_w = len(chars)*4 - 1
    col0 = 15 - total_w
    lit = set()
    for i,ch in enumerate(chars):
        pix = DIGITS[ch]
        for r in range(5):
            for c in range(3):
                if pix[r*3+c]: lit.add((3+r, col0+i*4+c))
    lit.add((3, col0+total_w+1))  # degree dot
    for r,c in lit:
        for dr,dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr,nc = r+dr,c+dc
            if (nr,nc) not in lit: px(f,nr,nc,(0,0,0))
    for r,c in lit: px(f,r,c,(255,255,255))

def fetch_weather():
    global w_temp, w_code, w_is_day, w_type, w_last, w_anim_start, w_tick
    if not wifi_ok: return
    url = ('https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}'
           '&current=temperature_2m,weathercode,is_day'
           '&temperature_unit=celsius').format(LAT, LON)
    try:
        r = urequests.get(url, timeout=10)
        data = r.json(); r.close()
        c = data['current']
        w_temp    = float(c['temperature_2m'])
        w_code    = int(c['weathercode'])
        w_is_day  = int(c['is_day'])
        new_type  = code_to_type(w_code, w_is_day)
        if new_type != w_type:
            w_type = new_type
            w_anim_start = w_tick
    except:
        pass
    w_last = utime.time()

def weather_frame():
    global w_refresh, w_tick
    if w_refresh or (utime.time() - w_last > REFRESH):
        w_refresh = False
        fetch_weather()
    f = ANIMS[w_type](w_tick - w_anim_start)
    if w_temp is not None:
        overlay_temp(f, w_temp)
    w_tick += 1
    return f

# ══════════════════════════════════════════════════════════════════
# SOUND VISUALIZER
# ══════════════════════════════════════════════════════════════════

mic = ADC(Pin(39))
mic.atten(ADC.ATTN_6DB)

def read_vol():
    samples = [mic.read() for _ in range(32)]
    return max(samples) - min(samples)

def sound_frame():
    vol = read_vol()
    height = min(8, vol * 8 // 400)
    f = [B] * 128
    for col in range(16):
        for row in range(height):
            if row < 3:   c = (255, 0, 0)
            elif row < 6: c = (0, 255, 0)
            else:         c = (0, 0, 255)
            f[(7 - row) * 16 + col] = c
    return f

# ══════════════════════════════════════════════════════════════════
# BUTTON HANDLERS
# ══════════════════════════════════════════════════════════════════

def on_btn_a():
    global pom_run, pom_last
    if APP == 0:
        pom_run = not pom_run
        if pom_run: pom_last = utime.time()

def on_btn_b():
    global pom_run, pom_left, w_refresh
    if APP == 0:
        pom_run = False; pom_left = pom_total
    elif APP == 1:
        w_refresh = True

def on_js_up():
    if APP == 0 and not pom_run: pom_change(+1)

def on_js_down():
    if APP == 0 and not pom_run: pom_change(-1)

pk.on_button_a    = on_btn_a
pk.on_button_b    = on_btn_b
pk.on_joystick_up = on_js_up
pk.on_joystick_down = on_js_down

# ══════════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════════

# Brief white flash so you know it's starting
pk.set_background((20, 20, 20)); pk.render(); utime.sleep(0.5)
pk.clear(); pk.render()

# Connect to home WiFi (needed for weather)
connect_wifi()
if wifi_ok:
    fetch_weather()

# ══════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════

while True:
    pk.check_controls()
    if APP == 0:
        pom_tick()
        show(pom_frame())
    elif APP == 1:
        show(weather_frame())
    else:
        show(sound_frame())
    utime.sleep(0.1)
