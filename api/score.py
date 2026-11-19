"""POST /api/score  {"text": "..."}  ->  {"scores": {aspek: skor|null}, "evidence": {aspek: [..]}}

Model kata kunci + TF-IDF/Ridge (murni Python, tanpa dependensi). Skala 1-5.
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import aspect_model as am  # noqa: E402

MAX_TEXT_CHARS = 3000
_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = am.load_model(am.DEFAULT_MODEL_PATH)
    return _MODEL


def find_spans(text: str, windows: list) -> list:
    """Posisi [awal, akhir] tiap jendela aspek pada teks asli (untuk penanda warna). Yang tidak ketemu dilewati."""
    spans = []
    for w in windows:
        if not w:
            continue
        m = re.search(r"[^a-z0-9]+".join(re.escape(t) for t in w), text, re.I)
        if m:
            spans.append([m.start(), m.end()])
    return spans


def score(text: str) -> dict:
    text = text[:MAX_TEXT_CHARS]
    detail = am.analyze(text, get_model())
    wins = am.extract_windows(text)
    return {
        "spans": {a: find_spans(text, wins.get(a) or []) for a in detail},
        "scores": {a: (None if d["score"] is None else round(d["score"], 2)) for a, d in detail.items()},
        "evidence": {a: d["evidence"] for a, d in detail.items()},
        "model": get_model().get("meta", {}),
    }


class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 100_000:
                return self._send(413, {"error": "Teks terlalu besar."})
            data = json.loads(self.rfile.read(n) or b"{}")
            text = str(data.get("text") or "").strip()
            if not text:
                return self._send(400, {"error": "Teks review kosong."})
            self._send(200, score(text))
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": f"Model gagal menilai: {type(e).__name__}: {e}"})

    def do_GET(self):
        self._send(200, {"ok": True, "info": "POST {text} ke endpoint ini."})
