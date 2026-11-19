import os, sys, pathlib, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["SECRETARY_DB"] = tempfile.mktemp(suffix=".db")
import numpy as np
from secretary.nlp import analyze, parse_transcript
from secretary.audio import diarize
from app import app

SAMPLE = (ROOT / "tests" / "sample_meeting.txt").read_text()

def test_parse_formats():
    assert [t.speaker for t in parse_transcript(SAMPLE)][:3] == ["Alice", "Bruno", "Chloé"]
    srt = "1\n00:00:01,000 --> 00:00:03,500\nAlice: Bonjour.\n\n2\n00:00:04,000 --> 00:00:06,000\nBob: Salut !\n"
    t = parse_transcript(srt); assert [x.speaker for x in t] == ["Alice", "Bob"] and t[0].end == 3.5

def test_report_content():
    r = analyze(parse_transcript(SAMPLE))
    assert any("décal" in d["text"] for d in r.decisions)
    owners = {t["owner"] for t in r.tasks}; assert {"Bruno", "Chloé"} <= owners
    assert any(t["deadline"] for t in r.tasks)
    assert 3 <= len(r.summary) <= 5 and r.speakers["Alice"]["share"] > 0.3

def test_diarize_two_voices():
    sr = 16000; t = np.arange(int(sr * 1.5)) / sr
    voice = lambda f0: sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 8)).astype(np.float32)
    a, b = voice(110), voice(240); x = np.concatenate([a, b, a, b, a, b]) * 0.3
    segs = [(i * 1.5, (i + 1) * 1.5) for i in range(6)]
    assert diarize(x, segs, sr=sr) == [0, 1, 0, 1, 0, 1]

def test_api_roundtrip():
    c = app.test_client()
    m = c.post("/api/transcript", json={"text": SAMPLE, "title": "Test"}).json
    assert m["id"] and "## Décisions" in m["markdown"]
    assert c.get(f"/api/meetings/{m['id']}").status_code == 200
    assert c.post("/api/transcript", json={"text": ""}).status_code == 400
