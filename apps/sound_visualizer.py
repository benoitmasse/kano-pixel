import sys
sys.path.insert(0, '/Users/ben/kano-sdk-python')

from communitysdk import list_connected_devices, RetailPixelKitSerial as PixelKit
import audioop
import pyaudio
import time

# --- Settings ---
SENSITIVITY = 2.0
NUM_COLS = 16
NUM_ROWS = 8
CHUNK = 1024
RATE = 44100

# --- Colors per row height (bottom to top: red -> green -> blue) ---
def get_color(row, max_row):
    if row < 3:
        return '#ff0000'  # red - low
    elif row < 6:
        return '#00ff00'  # green - mid
    else:
        return '#0000ff'  # blue - high

# --- Build a frame from 16 bar heights ---
def bars_to_frame(bar_heights):
    frame = ['#000000'] * 128
    for col in range(NUM_COLS):
        height = min(bar_heights[col], NUM_ROWS)
        for row in range(NUM_ROWS):
            pixel_row = NUM_ROWS - 1 - row  # flip: row 0 = bottom
            idx = pixel_row * NUM_COLS + col
            if row < height:
                frame[idx] = get_color(row, NUM_ROWS)
    return frame

# --- Connect to Pixel Kit ---
devices = list_connected_devices()
pk_filter = filter(lambda d: isinstance(d, PixelKit), devices)
pk = next(pk_filter, None)

if pk is None:
    print('No Pixel Kit found :(')
    sys.exit()

print('Pixel Kit connected! Listening to sound...')

# --- Audio setup ---
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1,
                rate=RATE, input=True, frames_per_buffer=CHUNK)

try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        rms = audioop.rms(data, 2)  # volume level
        
        # Spread volume across 16 bars with slight variation
        import random
        base = int((rms / 32768.0) * NUM_ROWS * SENSITIVITY * 8)
        bars = []
        for i in range(NUM_COLS):
            variation = random.randint(-1, 1)
            bars.append(max(0, min(NUM_ROWS, base + variation)))
        
        frame = bars_to_frame(bars)
        pk.stream_frame(frame)
        time.sleep(0.05)

except KeyboardInterrupt:
    print('Stopped.')
    stream.stop_stream()
    stream.close()
    p.terminate()
