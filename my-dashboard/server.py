#!/usr/bin/env python3
import argparse
import base64
import json
import os
import subprocess
import sys
import threading
import time
from io import BytesIO
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from my_dashboard import load_config, render_dashboard, default_config
from plugins import PLUGIN_DEFAULTS, PLUGIN_SCHEMAS, PLUGIN_NAMES

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
OUTPUT_DIR = BASE_DIR / ".generated"
SCRIPT_PATH = BASE_DIR / "my_dashboard.py"

_apply_lock = threading.Lock()
_apply_process = None
_apply_started_at = None
_apply_last_error = None
_apply_last_finished_at = None


def _progress_for_elapsed(elapsed):
    if elapsed < 5:
        return 20, "Rendering dashboard"
    if elapsed < 20:
        return 40, "Sending data to display"
    if elapsed < 40:
        return 65, "Refreshing display"
    return 85, "Finalizing"


def start_apply_process(cfg):
    global _apply_process, _apply_started_at, _apply_last_error, _apply_last_finished_at
    with _apply_lock:
        if _apply_process and _apply_process.poll() is None:
            return _apply_process, False
        try:
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
        except Exception:
            pass
        env = os.environ.copy()
        env["PYTHONPATH"] = str(BASE_DIR)
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=str(BASE_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _apply_process = process
        _apply_started_at = time.time()
        _apply_last_error = None
        _apply_last_finished_at = None

    def monitor():
        global _apply_process, _apply_last_error, _apply_last_finished_at
        stdout, stderr = process.communicate()
        with _apply_lock:
            if process.returncode != 0:
                _apply_last_error = (stderr or stdout or "Upload failed").strip()
            _apply_last_finished_at = time.time()
            _apply_process = None

    threading.Thread(target=monitor, daemon=True).start()
    return process, True


def get_apply_state():
    with _apply_lock:
        process = _apply_process
        started_at = _apply_started_at
        error = _apply_last_error
        finished_at = _apply_last_finished_at

    if process and process.poll() is None and started_at:
        elapsed = time.time() - started_at
        percent, message = _progress_for_elapsed(elapsed)
        return {
            "running": True,
            "percent": percent,
            "message": message,
            "started_at": started_at,
        }
    return {
        "running": False,
        "error": error,
        "finished_at": finished_at,
    }


def update_cron(schedule=None, minutes=None):
    schedule = (schedule or "").strip()
    command = f"{sys.executable} {SCRIPT_PATH}"
    try:
        existing = subprocess.run(
            ["crontab", "-l"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        lines = existing.stdout.splitlines() if existing.returncode == 0 else []
    except Exception as exc:
        return False, f"Failed to read crontab: {exc}"

    next_lines = [line for line in lines if command not in line]
    if minutes is not None:
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            return False, "Update frequency must be a whole number of minutes."
        if minutes < 1:
            return False, "Update frequency must be at least 1 minute."
        cron_line = "* * * * *" if minutes == 1 else f"*/{minutes} * * * *"
        next_lines.append(f"{cron_line} {command}")
    elif schedule:
        if schedule.startswith("@"):
            cron_line = f"{schedule} {command}"
        else:
            parts = schedule.split()
            if len(parts) != 5:
                return False, "Schedule must be a 5-field cron or @hourly style string."
            cron_line = f"{schedule} {command}"
        next_lines.append(cron_line)

    try:
        subprocess.run(
            ["crontab", "-"],
            input="\n".join(next_lines) + "\n",
            check=True,
            text=True,
        )
    except Exception as exc:
        return False, f"Failed to update crontab: {exc}"
    return True, "ok"


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR / "web"), **kwargs)

    def translate_path(self, path):
        clean_path = path.split("?", 1)[0].split("#", 1)[0]
        if clean_path.startswith("/generated/"):
            rel = clean_path[len("/generated/"):]
            return str((OUTPUT_DIR / rel).resolve())
        return super().translate_path(clean_path)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return None
        data = self.rfile.read(length)
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, event, payload):
        data = json.dumps(payload)
        message = f"event: {event}\ndata: {data}\n\n"
        self.wfile.write(message.encode("utf-8"))
        self.wfile.flush()

    def do_GET(self):
        if self.path.startswith("/api/apply/stream"):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            config_param = params.get("config", [""])[0]
            cfg = load_config()
            if config_param:
                try:
                    padding = "=" * (-len(config_param) % 4)
                    decoded = base64.urlsafe_b64decode(config_param + padding)
                    cfg = json.loads(decoded.decode("utf-8"))
                except Exception:
                    cfg = load_config()

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            state = get_apply_state()
            if not state["running"]:
                start_apply_process(cfg)
            while True:
                state = get_apply_state()
                if not state["running"]:
                    if state.get("error"):
                        self._send_sse("failed", {"message": state["error"]})
                    else:
                        self._send_sse("progress", {"percent": 95, "message": "Refresh complete"})
                        self._send_sse("done", {"message": "Upload complete"})
                    break
                self._send_sse(
                    "progress",
                    {"percent": state.get("percent", 20), "message": state.get("message", "Uploading...")},
                )
                time.sleep(2)
            self.close_connection = True
            return
        if self.path.startswith("/api/apply/status"):
            return self._send_json(get_apply_state())
        if self.path.startswith("/api/config"):
            cfg = load_config()
            return self._send_json(cfg)
        if self.path.startswith("/api/plugins"):
            return self._send_json({
                "defaults": PLUGIN_DEFAULTS,
                "schemas": PLUGIN_SCHEMAS,
                "names": PLUGIN_NAMES,
            })
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/config"):
            payload = self._read_json()
            if payload is None:
                return self._send_json({"error": "Invalid JSON"}, status=400)
            try:
                CONFIG_PATH.write_text(json.dumps(payload, indent=2))
                minutes = payload.get("update_interval_minutes")
                schedule = payload.get("update_schedule")
                if minutes is not None or schedule is not None:
                    ok, message = update_cron(schedule=schedule, minutes=minutes)
                    if not ok:
                        return self._send_json({"error": message}, status=400)
            except Exception:
                return self._send_json({"error": "Failed to save config"}, status=500)
            return self._send_json({"ok": True})

        if self.path.startswith("/api/preview"):
            payload = self._read_json()
            cfg = payload or load_config()
            image = render_dashboard(cfg, output_path=OUTPUT_DIR / "preview.png", upload=False)
            buffer = BytesIO()
            image.convert("RGB").save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            return self._send_json({
                "ok": True,
                "image": "/generated/preview.png",
                "image_data": f"data:image/png;base64,{encoded}",
            })

        if self.path.startswith("/api/apply"):
            payload = self._read_json()
            cfg = payload or load_config()
            try:
                start_apply_process(cfg)
            except Exception as exc:
                return self._send_json({"error": str(exc)}, status=500)
            return self._send_json({"ok": True, "running": True})

        return self._send_json({"error": "Not found"}, status=404)


def main():
    parser = argparse.ArgumentParser(description="My Dashboard HTTP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    host = args.host
    port = args.port
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Serving on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
