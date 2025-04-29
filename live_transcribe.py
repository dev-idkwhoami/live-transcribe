import os
import io
import sys
import json
import wave
import queue
import threading
import numpy as np
import sounddevice as sd
import openai
from dotenv import load_dotenv
from pystray import Icon, MenuItem as item, Menu
from PIL import Image, ImageDraw
from functools import partial
from time import sleep
from scipy.signal import resample
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

client = None

CONFIG_FILE = "config.json"
SAMPLE_RATE = None
audio_q = queue.Queue()
input_device_index = None
paused = False
selected_event = threading.Event()


# Signal handler for thread-safe GUI updates
class SignalHandler(QObject):
    update_text_signal = pyqtSignal(str)


signal_handler = None


class TransparentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel(self)
        self.label.setFont(QFont('Segoe UI', 14))
        self.label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 180); padding: 10px;")
        self.label.setWordWrap(True)
        self.label.setMinimumWidth(800)
        self.label.setText("🟡 Waiting for input...")

        self.setCentralWidget(self.label)
        self.move(100, 100)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = event.globalPos() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()


def update_text(text):
    if signal_handler:
        signal_handler.update_text_signal.emit(text)


def start_gui():
    global window
    window = TransparentWindow()
    update_text("🟡 Waiting for input...")
    app.exec_()


# === Audio and Device Management ===
def list_devices():
    devices = []
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] > 0 and d['hostapi'] == 0:  # hostapi 0 is usually Windows DirectSound
            try:
                # Try to get the device info - this will fail for disabled devices
                sd.check_input_settings(device=i)
                devices.append((i, d['name']))
            except sd.PortAudioError:
                continue
    return devices


def save_device(index):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"device_index": index}, f)


def load_device():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f).get("device_index", None)
    return None


def set_input_device(index, *args):
    global input_device_index, SAMPLE_RATE
    input_device_index = index
    save_device(index)
    device_info = sd.query_devices(index)
    SAMPLE_RATE = int(device_info['default_samplerate'])
    selected_event.set()
    print(f"[🔊] Selected input: {device_info['name']} @ {SAMPLE_RATE} Hz")


def resample_audio(audio_data, orig_sr, target_sr=16000):
    num_samples = round(len(audio_data) * target_sr / orig_sr)
    return resample(audio_data, num_samples).astype(np.int16)


def audio_callback(indata, frames, time, status):
    if status:
        print("[Audio Warning]", status)
    audio_q.put(indata.copy())


def record_audio():
    with sd.InputStream(
            samplerate=SAMPLE_RATE,
            device=input_device_index,
            channels=1,
            dtype='int16',
            blocksize=4000,
            callback=audio_callback
    ):
        print("🎙️ Recording started")
        threading.Event().wait()


# === Transcription Loop ===
def transcribe_loop():
    global paused
    while True:
        if paused:
            sleep(0.5)
            continue

        frames = [audio_q.get() for _ in range(20)]  # ~5s
        audio_chunk = np.concatenate(frames)

        if SAMPLE_RATE != 16000:
            audio_chunk = resample_audio(audio_chunk, SAMPLE_RATE, 16000)

        with io.BytesIO() as wav_io:
            with wave.open(wav_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_chunk.tobytes())
            wav_io.seek(0)
            wav_io.name = "audio.wav"

            try:
                response = client.audio.translations.create(
                    model="whisper-1",
                    file=wav_io,
                )
                text = response.text.strip()
                if text and text.lower() != "you":
                    print("📝", text)
                    update_text("🟢 " + text)
                else:
                    update_text("")
            except Exception as e:
                print("[Error]", e)
                update_text("🔴 API error.")


# === Tray Icon ===
def create_icon_image():
    img = Image.new('RGB', (64, 64), color='white')
    draw = ImageDraw.Draw(img)
    draw.ellipse((16, 16, 48, 48), fill='black')
    return img


def toggle_pause(icon, item):
    global paused
    paused = not paused
    item.text = "Resume" if paused else "Pause"
    update_text("⏸ Paused" if paused else "🟢 Resumed")


def build_tray():
    device_menu = [
        item(name, partial(set_input_device, idx)) for idx, name in list_devices()
    ]
    return Menu(
        item('Select Input Device', Menu(*device_menu)),
        item('Pause', toggle_pause),
        item('Quit', lambda icon, item: app.quit())
    )


def run_tray():
    icon = Icon("Transcriber", create_icon_image(), "Live Transcriber", build_tray())
    icon.run()


def create_initial_files():
    # Track if .env was newly created
    env_created = False

    # Create .env if it doesn't exist
    if not os.path.exists('.env'):
        with open('.env', 'w') as env_file:
            env_file.write('OPENAI_API_KEY=')
        print("📄 Created empty .env file")
        env_created = True

    # Create config.json if it doesn't exist
    if not os.path.exists('config.json'):
        initial_config = {
            "device_index": None
        }
        with open('config.json', 'w') as config_file:
            json.dump(initial_config, config_file, indent=2)
        print("📄 Created config.json with initial settings")

    # Exit if .env was created
    if env_created:
        print("\n⚠️ Please add your OpenAI API key to the .env file:")
        print("1. Open .env file")
        print("2. Add your API key after 'OPENAI_API_KEY='")
        print("3. Save the file and restart the program")
        sys.exit(1)


# === App Entry Point ===
if __name__ == "__main__":
    create_initial_files()

    load_dotenv()
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        # Initialize Qt Application
        app = QApplication([])

        # Create signal handler
        signal_handler = SignalHandler()

        # Create main window
        window = TransparentWindow()


        # Connect signal to label update
        def update_label(text):
            if window and window.label:
                window.label.setText(text)
                window.adjustSize()


        signal_handler.update_text_signal.connect(update_label)

        # Show window
        window.show()

        # Initialize audio device if previously saved
        saved_device = load_device()
        if saved_device is not None:
            set_input_device(saved_device)

        # Start background threads
        threading.Thread(target=transcribe_loop, daemon=True).start()
        threading.Thread(target=run_tray, daemon=True).start()

        if input_device_index is None:
            print("⏳ Waiting for input device selection...")
            selected_event.wait()

        # Start audio recording in background
        threading.Thread(target=record_audio, daemon=True).start()

        # Start Qt event loop
        app.exec_()

    except KeyboardInterrupt:
        print("\n👋 Exiting.")
    except Exception as e:
        print(f"Error: {e}")
