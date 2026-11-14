
import sys
import os
import sqlite3
import subprocess
import platform
from pathlib import Path
from datetime import datetime

import psutil
from dotenv import load_dotenv
from openai import OpenAI

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QLineEdit, QFrame, QProgressBar, QMessageBox
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB = DATA_DIR / "jarvis.db"

API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

client = OpenAI(api_key=API_KEY) if API_KEY else None


# ---------------- DATABASE ----------------

def initialize_database():
    with sqlite3.connect(DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def save_memory(note):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO memories(note, created_at) VALUES (?, ?)",
            (note, datetime.now().isoformat())
        )


def get_memories():
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT note FROM memories ORDER BY id DESC LIMIT 20"
        ).fetchall()


# ---------------- DESKTOP CONTROL ----------------

ALLOWED_APPS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"]
}


def open_application(name):
    name = name.lower().strip()

    if platform.system() != "Windows":
        return "Application launching is configured for Windows."

    if name not in ALLOWED_APPS:
        return "This application is not in the approved launch list."

    try:
        subprocess.Popen(ALLOWED_APPS[name], shell=False)
        return f"Opening {name}."
    except Exception as error:
        return f"Unable to open application: {error}"


# ---------------- FILE SEARCH ----------------

def search_files(keyword):
    keyword = keyword.lower().strip()

    if len(keyword) < 2:
        return "Enter at least two characters."

    locations = [
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Downloads"
    ]

    results = []

    for folder in locations:
        if not folder.exists():
            continue

        for root, dirs, files in os.walk(folder):
            dirs[:] = [
                d for d in dirs
                if d.lower() not in ["node_modules", ".venv", "venv"]
                and not d.startswith(".")
            ]

            for filename in files:
                if keyword in filename.lower():
                    results.append(str(Path(root) / filename))

                    if len(results) >= 30:
                        return "\n".join(results)

    return "\n".join(results) if results else "No matching files found."


# ---------------- AI WORKER ----------------

class AIWorker(QThread):
    response_ready = Signal(str)

    def __init__(self, message):
        super().__init__()
        self.message = message

    def run(self):
        try:
            local_result = self.process_command(self.message)

            if local_result is not None:
                self.response_ready.emit(local_result)
                return

            if not client:
                self.response_ready.emit(
                    "Please add your OpenAI API key in the .env file."
                )
                return

            memories = get_memories()
            memory_text = "\n".join(
                [item[0] for item in memories]
            )

            response = client.responses.create(
                model=MODEL,
                instructions=(
                    "You are JARVIS, a helpful desktop AI assistant. "
                    "Be professional, intelligent and concise. "
                    "Never claim to perform actions that were not actually performed. "
                    "Saved user memories:\n" + memory_text
                ),
                input=self.message
            )

            self.response_ready.emit(
                response.output_text or "No response received."
            )

        except Exception as error:
            self.response_ready.emit(
                f"AI error: {error}"
            )

    def process_command(self, message):
        text = message.strip()
        lower = text.lower()

        if lower.startswith("open "):
            return open_application(text[5:])

        if lower.startswith("remember "):
            note = text[9:].strip()

            if note:
                save_memory(note)
                return "I have saved that note in local memory."

            return "Please tell me what to remember."

        if lower in ["show memory", "what do you remember"]:
            memories = get_memories()

            if not memories:
                return "Your memory is currently empty."

            return "My memories:\n" + "\n".join(
                f"• {item[0]}" for item in memories
            )

        if lower.startswith("find file "):
            return search_files(text[10:])

        if lower.startswith("search files "):
            return search_files(text[13:])

        if lower in ["system status", "check my pc"]:
            return (
                f"CPU Usage: {psutil.cpu_percent(interval=0.3)}%\n"
                f"RAM Usage: {psutil.virtual_memory().percent}%\n"
                f"Operating System: {platform.system()}"
            )

        return None


# ---------------- VOICE INPUT ----------------

class VoiceWorker(QThread):
    recognized = Signal(str)
    error = Signal(str)

    def run(self):
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()

            with sr.Microphone() as source:
                self.error.emit("Listening...")
                recognizer.adjust_for_ambient_noise(
                    source, duration=0.5
                )
                audio = recognizer.listen(
                    source, timeout=6, phrase_time_limit=12
                )

            text = recognizer.recognize_google(audio)
            self.recognized.emit(text)

        except Exception as error:
            self.error.emit(f"Voice error: {error}")


# ---------------- MAIN WINDOW ----------------

class JARVIS(QMainWindow):

    def __init__(self):
        super().__init__()

        initialize_database()

        self.setWindowTitle("J.A.R.V.I.S. Desktop Assistant")
        self.resize(1250, 800)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #050b13;
                color: #d8f7ff;
                font-family: Segoe UI;
            }

            QFrame#panel {
                background: #091522;
                border: 1px solid #12506a;
                border-radius: 12px;
            }

            QLabel#heading {
                color: #58e6ff;
                font-size: 27px;
                font-weight: bold;
                letter-spacing: 4px;
            }

            QPushButton {
                background: #0c293a;
                color: #8deaff;
                border: 1px solid #17617c;
                border-radius: 7px;
                padding: 11px;
            }

            QPushButton:hover {
                background: #10506b;
            }

            QLineEdit {
                background: #07111c;
                border: 1px solid #17617c;
                border-radius: 8px;
                padding: 13px;
                color: white;
            }

            QTextEdit {
                background: #06101a;
                border: 1px solid #12394d;
                border-radius: 8px;
                color: #d8f7ff;
                padding: 12px;
            }

            QProgressBar {
                background: #07111c;
                border: 1px solid #17617c;
                border-radius: 5px;
                text-align: center;
                height: 12px;
            }

            QProgressBar::chunk {
                background: #12b8d6;
                border-radius: 5px;
            }
        """)

        self.build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_system)
        self.timer.start(2000)

        self.update_system()

        self.add_message(
            "JARVIS",
            "Good day! All available systems are online. How may I assist you?"
        )

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main = QVBoxLayout(central)
        main.setContentsMargins(22, 20, 22, 20)
        main.setSpacing(15)

        # HEADER

        header = QHBoxLayout()

        title = QLabel("J.A.R.V.I.S.")
        title.setObjectName("heading")

        self.clock = QLabel()
        self.clock.setStyleSheet(
            "color:#58e6ff;font-size:22px;font-weight:bold;"
        )

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.clock)

        main.addLayout(header)

        # MAIN PANELS

        content = QHBoxLayout()
        content.setSpacing(15)

        # LEFT PANEL

        left = QFrame()
        left.setObjectName("panel")

        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("SYSTEM MONITOR"))

        self.cpu_label = QLabel("CPU: 0%")
        self.ram_label = QLabel("RAM: 0%")

        self.cpu_bar = QProgressBar()
        self.ram_bar = QProgressBar()

        left_layout.addWidget(self.cpu_label)
        left_layout.addWidget(self.cpu_bar)
        left_layout.addWidget(self.ram_label)
        left_layout.addWidget(self.ram_bar)

        left_layout.addSpacing(20)
        left_layout.addWidget(QLabel("APPLICATION CONTROL"))

        for app in ["Notepad", "Calculator", "Paint", "File Explorer"]:
            button = QPushButton("OPEN " + app.upper())
            button.clicked.connect(
                lambda checked=False, a=app: self.quick_command(
                    "open " + a
                )
            )
            left_layout.addWidget(button)

        left_layout.addSpacing(15)

        voice_button = QPushButton("🎙  VOICE COMMAND")
        voice_button.clicked.connect(self.listen)
        left_layout.addWidget(voice_button)

        left_layout.addStretch()

        # RIGHT PANEL

        right = QFrame()
        right.setObjectName("panel")

        right_layout = QVBoxLayout(right)

        right_layout.addWidget(QLabel("AI ASSISTANT"))

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)

        right_layout.addWidget(self.chat)

        input_row = QHBoxLayout()

        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Ask JARVIS anything..."
        )
        self.input.returnPressed.connect(self.send)

        send_button = QPushButton("SEND")
        send_button.clicked.connect(self.send)

        input_row.addWidget(self.input)
        input_row.addWidget(send_button)

        right_layout.addLayout(input_row)

        content.addWidget(left, 1)
        content.addWidget(right, 3)

        main.addLayout(content)

        self.status = QLabel("SYSTEM STATUS: READY")
        self.status.setStyleSheet("color:#58e6ff;")

        main.addWidget(self.status)

    # ---------------- CHAT ----------------

    def add_message(self, sender, message):
        color = "#58e6ff" if sender == "JARVIS" else "#f5b65c"

        safe = (
            message.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

        self.chat.append(
            f'<p><b style="color:{color}">{sender}</b><br>{safe}</p>'
        )

    def send(self):
        message = self.input.text().strip()

        if not message:
            return

        self.input.clear()

        self.add_message("YOU", message)

        self.status.setText("PROCESSING REQUEST...")

        self.worker = AIWorker(message)
        self.worker.response_ready.connect(self.reply)
        self.worker.start()

    def quick_command(self, command):
        self.input.setText(command)
        self.send()

    def reply(self, response):
        self.add_message("JARVIS", response)
        self.status.setText("SYSTEM STATUS: READY")

        if os.getenv("JARVIS_SPEAK", "0") == "1":
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(response[:1000])
                engine.runAndWait()
            except Exception:
                pass

    # ---------------- VOICE ----------------

    def listen(self):
        self.status.setText("LISTENING...")

        self.voice_worker = VoiceWorker()
        self.voice_worker.recognized.connect(self.voice_result)
        self.voice_worker.error.connect(self.voice_error)
        self.voice_worker.start()

    def voice_result(self, text):
        self.input.setText(text)
        self.status.setText("VOICE RECEIVED")
        self.send()

    def voice_error(self, message):
        self.status.setText(message)

    # ---------------- MONITOR ----------------

    def update_system(self):
        self.clock.setText(datetime.now().strftime("%H:%M:%S"))

        self.cpu = psutil.cpu_percent()
        self.ram = psutil.virtual_memory().percent

        self.cpu_label.setText(f"CPU USAGE: {self.cpu}%")
        self.ram_label.setText(f"RAM USAGE: {self.ram}%")

        self.cpu_bar.setValue(int(self.cpu))
        self.ram_bar.setValue(int(self.ram))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = JARVIS()
    window.show()

    sys.exit(app.exec())
