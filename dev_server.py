"""Server lokal untuk mencoba website + API tanpa Vercel.   Jalankan: python dev_server.py   lalu buka http://localhost:8000
(Opsional: set GEMINI_API_KEY di terminal untuk mencoba kesimpulan Gemini.)"""
import importlib.util
import os
import types
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "api", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.handler


ROUTES = {"/api/score": load("score"), "/api/summary": load("summary")}


class Dev(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=os.path.join(ROOT, "public"), **k)

    def _api(self, method):
        h = ROUTES.get(self.path.split("?")[0])
        if h is None:
            return self.send_error(404)
        self._send = types.MethodType(h._send, self)
        getattr(h, method)(self)

    def do_POST(self):
        self._api("do_POST")

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api("do_GET")
        super().do_GET()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Buka http://localhost:{port}")
    HTTPServer(("", port), Dev).serve_forever()
