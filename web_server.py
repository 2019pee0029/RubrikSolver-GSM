"""Local static server and native cube-solver API."""

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from main import CubeState, apply_sequence, verify_state
from solver import inverse_sequence, solve

PROJECT_ROOT = Path(__file__).resolve().parent
MAX_HISTORY_LENGTH = 10000


class CubeRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self):
        if urlsplit(self.path).path == "/api/health":
            self._send_json(200, {"ready": True})
            return
        super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path != "/api/solve":
            self._send_json(404, {"error": "Unknown endpoint."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 1_000_000:
                raise ValueError("Invalid request size.")
            payload = json.loads(self.rfile.read(content_length))
            moves = payload.get("moves")
            if not isinstance(moves, list) or len(moves) > MAX_HISTORY_LENGTH:
                raise ValueError("Expected a list of up to 10000 move tokens.")
            if any(not isinstance(move, str) for move in moves):
                raise ValueError("Every move token must be a string.")

            state = apply_sequence(CubeState.solved(), " ".join(moves))
            if not verify_state(state):
                raise ValueError("The submitted move history produced an invalid cube state.")

            fallback = inverse_sequence(moves)
            solution = solve(state, fallback_solution=fallback)
            strategy = "fallback" if solution == fallback else "two-phase"
            self._send_json(200, {"moves": solution, "strategy": strategy})
        except (json.JSONDecodeError, ValueError) as error:
            self._send_json(400, {"error": str(error)})
        except Exception as error:
            self._send_json(500, {"error": f"Solver error: {error}"})

    def _send_json(self, status, payload):
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(response)


def main():
    parser = argparse.ArgumentParser(description="Serve the Rubik viewer and native solver API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), CubeRequestHandler)
    server.daemon_threads = True
    print(f"Rubik viewer and native solver listening at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()