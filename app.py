import os, re, sqlite3, subprocess, platform, webbrowser
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
from openai import OpenAI

load_dotenv()
ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "jarvis.db"
app = Flask(__name__)
api_key = os.getenv("OPENAI_API_KEY", "").strip()
client = OpenAI(api_key=api_key) if api_key else None
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

SYSTEM = """You are JARVIS, a calm, capable desktop AI assistant. Be helpful and concise.
You can use tools exposed by this application for allowlisted app launching, filename search,
local notes/memory, weather, and news. Never claim an action succeeded unless the tool result
confirms it. Never request passwords, API secrets, or private keys in chat. Ask for confirmation
before any consequential external action. You cannot send email, change calendars, control smart
home devices, or identify a person unless those integrations are explicitly configured."""

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    DB.parent.mkdir(exist_ok=True)
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS memories(
            id INTEGER PRIMARY KEY AUTOINCREMENT, note TEXT NOT NULL,
            created_at TEXT NOT NULL)""")

init_db()

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/status")
def status():
    return jsonify({
        "ai_configured": bool(client),
        "desktop": os.getenv("JARVIS_DESKTOP", "0") == "1",
        "platform": platform.system()
    })

@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return jsonify(error="Enter a message first."), 400
    if not client:
        return jsonify(error="AI is not configured. Add OPENAI_API_KEY to your .env file and restart."), 503
    safe = []
    for m in messages[-14:]:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
            safe.append({"role": m["role"], "content": m["content"][:5000]})
    if not safe or safe[-1]["role"] != "user":
        return jsonify(error="Invalid conversation."), 400
    try:
        result = client.responses.create(model=MODEL, instructions=SYSTEM, input=safe)
        return jsonify(reply=result.output_text)
    except Exception:
        app.logger.exception("OpenAI request failed")
        return jsonify(error="AI request failed. Check API key, model name, internet, and API account."), 502

# Desktop actions are deliberately allowlisted; arbitrary shell commands are not accepted.
APP_TARGETS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "file explorer": ["explorer.exe"],
    "explorer": ["explorer.exe"],
}

@app.post("/api/launch")
def launch():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip().lower()
    if name not in APP_TARGETS:
        return jsonify(error="That application is not in the safe launch list."), 400
    if platform.system() != "Windows":
        return jsonify(error="This starter launcher currently supports Windows only.")
    try:
        subprocess.Popen(APP_TARGETS[name], shell=False)
        return jsonify(message=f"Launching {name}.")
    except Exception:
        app.logger.exception("Application launch failed")
        return jsonify(error=f"Could not launch {name}."), 500

@app.post("/api/files/search")
def file_search():
    data = request.get_json(silent=True) or {}
    term = str(data.get("term", "")).strip().lower()
    if len(term) < 2:
        return jsonify(error="Enter at least two characters."), 400
    home = Path.home()
    allowed = [home / "Desktop", home / "Documents", home / "Downloads"]
    found = []
    try:
        for folder in allowed:
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                if len(found) >= 30:
                    break
                if path.is_file() and term in path.name.lower():
                    found.append({"name": path.name, "folder": folder.name, "path": str(path)})
    except (PermissionError, OSError):
        pass
    return jsonify(results=found, searched=["Desktop", "Documents", "Downloads"])

@app.post("/api/memory")
def memory_add():
    data = request.get_json(silent=True) or {}
    note = str(data.get("note", "")).strip()
    if not note or len(note) > 1500:
        return jsonify(error="Memory must be between 1 and 1500 characters."), 400
    with db() as con:
        cur = con.execute("INSERT INTO memories(note, created_at) VALUES(?, ?)",
                          (note, datetime.now().isoformat(timespec="seconds")))
        return jsonify(id=cur.lastrowid, message="Saved to local JARVIS memory.")

@app.get("/api/memory")
def memory_list():
    with db() as con:
        rows = con.execute("SELECT id, note, created_at FROM memories ORDER BY id DESC LIMIT 50").fetchall()
    return jsonify(memories=[dict(r) for r in rows])

@app.delete("/api/memory/<int:memory_id>")
def memory_delete(memory_id):
    with db() as con:
        con.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    return jsonify(message="Memory deleted.")

@app.get("/api/weather")
def weather():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify(error="Enter a city."), 400
    try:
        g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1, "language": "en", "format": "json"}, timeout=12)
        g.raise_for_status()
        results = g.json().get("results", [])
        if not results:
            return jsonify(error=f"Could not find {city}."), 404
        p = results[0]
        w = requests.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": p["latitude"], "longitude": p["longitude"],
                                 "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m",
                                 "timezone": "auto"}, timeout=12)
        w.raise_for_status()
        c = w.json()["current"]
        return jsonify(city=p["name"], region=p.get("admin1", ""), temperature=c.get("temperature_2m"),
                       feels_like=c.get("apparent_temperature"), humidity=c.get("relative_humidity_2m"),
                       wind=c.get("wind_speed_10m"))
    except requests.RequestException:
        return jsonify(error="Weather service is unavailable."), 502

@app.get("/api/news")
def news():
    # Uses a public RSS feed. This is headlines-only, not a full web research engine.
    try:
        import xml.etree.ElementTree as ET
        response = requests.get("https://feeds.bbci.co.uk/news/world/rss.xml", timeout=12,
                                headers={"User-Agent": "JARVIS-Assistant/1.0"})
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = []
        for item in root.findall(".//item")[:10]:
            items.append({"title": item.findtext("title", default=""),
                          "link": item.findtext("link", default=""),
                          "published": item.findtext("pubDate", default="")})
        return jsonify(items=items)
    except Exception:
        return jsonify(error="Could not load news right now."), 502

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
