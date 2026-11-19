"""Silent Secretary — serveur Flask (API + interface)."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from dataclasses import asdict
from datetime import datetime

from flask import Flask, g, jsonify, request, send_from_directory

from secretary import audio
from secretary.nlp import Turn, analyze, parse_transcript, to_markdown

DB = os.environ.get("SECRETARY_DB", os.path.join(os.path.dirname(__file__), "secretary.db"))
app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("""CREATE TABLE IF NOT EXISTS meetings(id INTEGER PRIMARY KEY, title TEXT, created TEXT,
                        turns TEXT, report TEXT)""")
    return g.db


@app.teardown_appcontext
def close(_):
    if "db" in g:
        g.db.close()


def build(title: str, turns: list[Turn], mid: int | None = None) -> dict:
    rep = analyze(turns)
    created = datetime.now().strftime("%d/%m/%Y %H:%M")
    payload = {"title": title, "created": created, "turns": [asdict(t) for t in turns], "report": asdict(rep)}
    payload["markdown"] = to_markdown(title, created, turns, rep)
    con = db()
    if mid:
        con.execute("UPDATE meetings SET title=?, turns=?, report=? WHERE id=?", (title, json.dumps(payload["turns"]), json.dumps(payload["report"]), mid))
    else:
        mid = con.execute("INSERT INTO meetings(title, created, turns, report) VALUES(?,?,?,?)",
                          (title, created, json.dumps(payload["turns"]), json.dumps(payload["report"]))).lastrowid
    con.commit()
    payload["id"] = mid
    return payload


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/info")
def info():
    return jsonify({"whisper": audio.whisper_available()})


@app.post("/api/transcript")
def from_transcript():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if "turns" in data:  # transcription live depuis le navigateur
        turns = [Turn(t.get("speaker", "?"), t.get("text", ""), t.get("start"), t.get("end")) for t in data["turns"] if t.get("text")]
    else:
        turns = parse_transcript(text)
    if not turns:
        return jsonify({"error": "Transcription vide"}), 400
    return jsonify(build(data.get("title") or "Réunion sans titre", turns, data.get("id")))


@app.post("/api/audio")
def from_audio():
    f = request.files.get("audio")
    if not f:
        return jsonify({"error": "Aucun fichier audio"}), 400
    if not audio.whisper_available():
        return jsonify({"error": "Whisper n'est pas installé sur le serveur. Utilisez la dictée en direct ou importez une transcription."}), 501
    suffix = os.path.splitext(f.filename or "a.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
    try:
        segs = audio.transcribe(tmp.name, request.form.get("model", "base"), request.form.get("lang") or None)
    finally:
        os.unlink(tmp.name)
    turns = [Turn(s["speaker"], s["text"], s["start"], s["end"]) for s in segs]
    return jsonify(build(request.form.get("title") or f.filename, turns))


@app.get("/api/meetings")
def meetings():
    rows = db().execute("SELECT id, title, created FROM meetings ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/meetings/<int:mid>")
def meeting(mid):
    r = db().execute("SELECT * FROM meetings WHERE id=?", (mid,)).fetchone()
    if not r:
        return jsonify({"error": "introuvable"}), 404
    turns = [Turn(**t) for t in json.loads(r["turns"])]
    rep = json.loads(r["report"])
    from secretary.nlp import Report
    return jsonify({"id": r["id"], "title": r["title"], "created": r["created"], "turns": json.loads(r["turns"]), "report": rep,
                    "markdown": to_markdown(r["title"], r["created"], turns, Report(**rep))})


@app.put("/api/meetings/<int:mid>/report")
def save_report(mid):
    """Enregistre les modifications faites dans l'interface (tâches cochées, responsables…)."""
    rep = request.get_json()
    db().execute("UPDATE meetings SET report=? WHERE id=?", (json.dumps(rep), mid))
    db().commit()
    return jsonify({"ok": True})


@app.delete("/api/meetings/<int:mid>")
def delete(mid):
    db().execute("DELETE FROM meetings WHERE id=?", (mid,))
    db().commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5003))
    print(f"Silent Secretary → http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port)
