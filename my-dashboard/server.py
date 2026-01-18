#!/usr/bin/env python3
import argparse
import base64
import json
import subprocess
import sys
from io import BytesIO
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from my_dashboard import load_config, render_dashboard, default_config
from plugins import PLUGIN_DEFAULTS, PLUGIN_SCHEMAS, PLUGIN_NAMES

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
OUTPUT_DIR = BASE_DIR / ".generated"
SCRIPT_PATH = BASE_DIR / "my_dashboard.py"


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

    def do_GET(self):
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
            render_dashboard(cfg, output_path=OUTPUT_DIR / "dashboard.png", upload=True)
            return self._send_json({"ok": True, "image": "/generated/dashboard.png"})

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
