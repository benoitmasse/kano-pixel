# kano-pixel

Apps for the Kano Pixel Kit, built with the [community SDK](https://github.com/KanoComputing/kano-sdk-python).

## Apps

- **pomodoro.py** — Pomodoro timer displayed on the Pixel Kit. Btn-A: start/pause, Btn-B: reset, joystick up/down: change preset duration.
- **sound_visualizer.py** — Real-time sound visualizer that maps microphone volume to a 16-column bar graph on the Pixel Kit.

## Requirements

- [kano-sdk-python](https://github.com/KanoComputing/kano-sdk-python) installed at `/Users/ben/kano-sdk-python`
- `pyaudio` (for sound_visualizer)

## Usage

```bash
python apps/pomodoro.py
python apps/sound_visualizer.py
```
