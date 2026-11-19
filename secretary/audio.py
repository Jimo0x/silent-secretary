"""Transcription audio (Whisper, optionnel) et séparation des intervenants.

La diarisation est volontairement légère : chaque segment est décrit par son
empreinte spectrale (énergie par bandes) et sa hauteur de voix, puis les
segments sont regroupés par K-means. Le nombre d'intervenants est choisi
automatiquement par le score de silhouette.
"""
from __future__ import annotations

import shutil
import subprocess

import numpy as np

SR = 16000

try:
    import whisper  # type: ignore
except Exception:  # pragma: no cover
    whisper = None


def whisper_available() -> bool:
    return whisper is not None and shutil.which("ffmpeg") is not None


def load_audio(path: str) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-nostdin", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768.0


def voice_features(x: np.ndarray, sr: int = SR) -> np.ndarray:
    """Empreinte d'un segment : 24 bandes log-énergie normalisées + hauteur (F0) + centroïde."""
    if len(x) < sr // 10:
        x = np.pad(x, (0, sr // 10 - len(x)))
    n = 1024
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[:: n // 2] * np.hanning(n)
    spec = np.abs(np.fft.rfft(frames, axis=1)) ** 2
    energy = spec.sum(axis=1)
    voiced = spec[energy > np.percentile(energy, 40)] if len(spec) > 4 else spec
    freqs = np.fft.rfftfreq(n, 1 / sr)
    edges = np.geomspace(80, 7600, 25)
    bands = np.array([voiced[:, (freqs >= lo) & (freqs < hi)].sum(axis=1).mean() for lo, hi in zip(edges[:-1], edges[1:])])
    bands = np.log1p(bands)
    bands = (bands - bands.mean()) / (bands.std() + 1e-9)
    centroid = float((voiced * freqs).sum() / (voiced.sum() + 1e-9))
    # F0 par autocorrélation sur la trame la plus énergique
    f = frames[int(np.argmax(energy))]
    ac = np.correlate(f, f, "full")[n - 1:]
    lo, hi = sr // 400, sr // 70
    f0 = sr / (lo + int(np.argmax(ac[lo:hi]))) if ac[0] > 0 else 0.0
    return np.concatenate([bands, [f0 / 100.0, centroid / 1000.0]])


def diarize(x: np.ndarray, segments: list[tuple[float, float]], max_speakers: int = 4, sr: int = SR) -> list[int]:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    if len(segments) < 3:
        return [0] * len(segments)
    feats = np.array([voice_features(x[int(a * sr): int(b * sr)], sr) for a, b in segments])
    feats = (feats - feats.mean(0)) / (feats.std(0) + 1e-9)
    best, best_s = [0] * len(segments), 0.12  # en dessous : un seul intervenant
    for k in range(2, min(max_speakers, len(segments) - 1) + 1):
        lab = KMeans(k, n_init=10, random_state=0).fit_predict(feats)
        s = silhouette_score(feats, lab)
        if s > best_s:
            best, best_s = list(lab), s
    # renumérotation dans l'ordre d'apparition
    order: dict[int, int] = {}
    return [order.setdefault(int(l), len(order)) for l in best]


def transcribe(path: str, model: str = "base", language: str | None = None) -> list[dict]:
    if not whisper_available():
        raise RuntimeError("Whisper n'est pas installé (pip install openai-whisper) ou ffmpeg est introuvable.")
    m = whisper.load_model(model)
    res = m.transcribe(path, language=language, fp16=False)
    segs = [(s["start"], s["end"]) for s in res["segments"]]
    labels = diarize(load_audio(path), segs)
    return [{"speaker": f"Intervenant {l + 1}", "text": s["text"].strip(), "start": s["start"], "end": s["end"]}
            for s, l in zip(res["segments"], labels)]
