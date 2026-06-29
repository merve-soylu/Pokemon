import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from config import API_HOST, API_PORT, STATE_FILE, PRODUCTS_FILE
from logger import log
from storage import save_json
from tracker import process_product


class TrackerApiHandler(BaseHTTPRequestHandler):
    state = None
    products_db = None

    def log_message(self, format, *args):
        return

    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"ok": True})
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/ebgames/products":
            self._send_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw)

            products = payload.get("products", [])

            results = {
                "received": len(products),
                "new_pinged": 0,
                "new_no_ping": 0,
                "updated_pinged": 0,
                "updated_no_ping": 0,
                "seen": 0,
                "ignored": 0,
            }

            for product in products:
                product["ignored"] = False
                product["booster_ok"] = True

                result = process_product(
                    TrackerApiHandler.state,
                    TrackerApiHandler.products_db,
                    "EB Games",
                    product,
                )

                if result in results:
                    results[result] += 1

            save_json(STATE_FILE, TrackerApiHandler.state)
            save_json(PRODUCTS_FILE, TrackerApiHandler.products_db)

            log("API", f"EB products received: {results}")
            self._send_json(200, {"ok": True, "results": results})

        except Exception as e:
            log("ERROR", f"API failed: {e}")
            self._send_json(500, {"ok": False, "error": str(e)})


class ApiServer:
    def __init__(self, state, products_db):
        self.server = None
        self.thread = None

        TrackerApiHandler.state = state
        TrackerApiHandler.products_db = products_db

    def start(self):
        self.server = ThreadingHTTPServer((API_HOST, API_PORT), TrackerApiHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        log("API", f"Listening on http://{API_HOST}:{API_PORT}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()