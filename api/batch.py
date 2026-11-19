"""POST /api/batch  {"texts": ["review 1", "review 2", ...]}  ->  {"n": N, "results": [{aspek: skor|null}, ...]}

Menilai banyak review sekaligus (untuk fitur Profil Hotel). Maksimal 100 review, tiap review dipotong 1.500 karakter.
Model sama dengan /api/score (murni Python, tanpa dependensi).
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import aspect_model as am  # noqa: E402

MAX_TEXTS = 100
MAX_CHARS = 1500
MAX_BODY = 400_000
_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = am.load_model(am.DEFAULT_MODEL_PATH)
    return _MODEL


def score_many(texts: list) -> list:
    m = get_model()
    out = []
    for t in texts[:MAX_TEXTS]:
        d = am.analyze(str(t)[:MAX_CHARS], m)
        out.append({a: (None if r["score"] is None else round(r["score"], 2)) for a, r in d.items()})
    return out


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
            if n > MAX_BODY:
                return self._send(413, {"error": "Data terlalu besar. Maksimal 100 review per analisis."})
            data = json.loads(self.rfile.read(n) or b"{}")
            texts = [str(t).strip() for t in (data.get("texts") or []) if str(t).strip()]
            if not texts:
                return self._send(400, {"error": "Belum ada review."})
            res = score_many(texts)
            self._send(200, {"n": len(res), "results": res})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": f"Model gagal menilai: {type(e).__name__}: {e}"})

    def do_GET(self):
        self._send(200, {"ok": True, "info": "POST {texts: [...]} ke endpoint ini."})
