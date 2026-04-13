import sys
import subprocess
sys.path.insert(0, '/Users/ben/kano-sdk-python')

from communitysdk import list_connected_devices, RetailPixelKitSerial as PixelKit
from time import sleep, time

minutes = 15
total_seconds = minutes * 60
seconds_left = total_seconds
running = False
last_tick = None

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
}

def play_sound(name):
    subprocess.Popen(['afplay', '/System/Library/Sounds/{}.aiff'.format(name)])

def get_color(seconds_left, total, is_running):
    if not is_running:
        return '#ff8800'
    ratio = seconds_left / total
    if ratio > 0.5:
        return '#00ff00'
    elif ratio > 0.25:
        return '#ffff00'
    else:
        return '#ff0000'

def draw_digit(frame, digit, col_offset, color):
    pixels = DIGITS[digit]
    for row in range(5):
        for col in range(3):
            idx = (row + 1) * 16 + col_offset + col
            if pixels[row * 3 + col]:
                frame[idx] = color

def build_frame(seconds_left, total_seconds, is_running):
    frame = ['#000000'] * 128
    color = get_color(seconds_left, total_seconds, is_running)
    mins = seconds_left // 60
    secs = seconds_left % 60
    draw_digit(frame, str(mins // 10), 0, color)
    draw_digit(frame, str(mins % 10), 4, color)
    frame[2 * 16 + 7] = color
    frame[4 * 16 + 7] = color
    draw_digit(frame, str(secs // 10), 8, color)
    draw_digit(frame, str(secs % 10), 12, color)
    progress = int((seconds_left / total_seconds) * 16)
    for i in range(progress):
        frame[7 * 16 + i] = color
    return frame

def flash_done(pk):
    play_sound('Hero')
    for _ in range(6):
        pk.stream_frame(['#ffffff'] * 128)
        sleep(0.2)
        pk.stream_frame(['#000000'] * 128)
        sleep(0.2)

def change_minutes(direction):
    global minutes, total_seconds, seconds_left
    step = 1 if minutes < 10 else 5
    minutes = max(1, min(60, minutes + direction * step))
    total_seconds = minutes * 60
    seconds_left = total_seconds

devices = list_connected_devices()
pk = next(filter(lambda d: isinstance(d, PixelKit), devices), None)

if pk is None:
    print('No Pixel Kit found :(')
    sys.exit()

print('Connected! btn-A: Start/Pause | btn-B: Reset | js-up/down: change duration')
print('Current: {} min'.format(minutes))

def on_button_down(button_id):
    global running, last_tick, seconds_left, total_seconds, minutes
    if button_id == 'btn-A':
        running = not running
        if running:
            last_tick = time()
            play_sound('Ping')
            print('Started!')
        else:
            print('Paused.')
    elif button_id == 'btn-B':
        running = False
        seconds_left = total_seconds
        print('Reset to {} min'.format(minutes))
    elif button_id == 'js-up' and not running:
        change_minutes(+1)
        print('Duration: {} min'.format(minutes))
    elif button_id == 'js-down' and not running:
        change_minutes(-1)
        print('Duration: {} min'.format(minutes))

pk.on_button_down = on_button_down

try:
    while True:
        if running:
            now = time()
            elapsed = now - last_tick
            if elapsed >= 1.0:
                seconds_left -= int(elapsed)
                last_tick = now
                if seconds_left <= 0:
                    seconds_left = 0
                    running = False
                    print('Done!')
                    flash_done(pk)
        pk.stream_frame(build_frame(seconds_left, total_seconds, running))
        sleep(0.1)
except KeyboardInterrupt:
    print('Stopped.')
