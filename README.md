# Raspberry Inky Projects

## Raspberry Pi setup

1. Enable SSH and SPI on the Pi:
   - `sudo raspi-config`
   - Interface Options → SSH → Enable
   - Interface Options → SPI → Enable

2. Install system packages:
   - `sudo apt-get update`
   - `sudo apt-get install -y python3 python3-venv python3-pip git rsync libcairo2 libpango-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev`

3. Create the virtual environment and install Python dependencies:
   - `python3 -m venv /home/hazam/inky-venv`
   - `/home/hazam/inky-venv/bin/pip install --upgrade pip`
   - `/home/hazam/inky-venv/bin/pip install -r /home/hazam/projects/my-dashboard/requirements.txt`
   - Or run `my-dashboard/scripts/install_deps.sh` to do steps 2-3 in one shot.

4. Configure SSH host alias on your workstation (`~/.ssh/config`):
   - `Host inky`
   - `  HostName <pi-ip-address>`
   - `  User hazam`

5. Sync the dashboard code to the Pi:
   - `./sync_to_inky.sh`
   - To overwrite the runtime config on the Pi: `SYNC_CONFIG=1 ./sync_to_inky.sh`

## Config files

- `my-dashboard/config.default.json` is the tracked default config.
- `my-dashboard/config.json` is the local runtime config (gitignored, saved by the UI).

### Dithering options

You can enable dithering for the layout background and borders in `config.json`:

```json
{
  "layout": {
    "background": {
      "color": "white",
      "dither": true,
      "dither_color": "blue",
      "dither_step": 2,
      "dither_ratio": 0.5
    },
    "border": {
      "dither": true,
      "dither_color": "white",
      "dither_step": 2,
      "dither_ratio": 0.5
    }
  }
}
```

## Auto-start the HTTP server

Create the service on the Pi at `/etc/systemd/system/my-dashboard-http.service`:

```
[Unit]
Description=My Dashboard HTTP Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/hazam/projects/my-dashboard
ExecStart=/home/hazam/inky-venv/bin/python /home/hazam/projects/my-dashboard/server.py --port 80
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
Restart=on-failure
User=hazam

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```
sudo systemctl daemon-reload
sudo systemctl enable --now my-dashboard-http.service
```

## Deploy script

Use the helper to sync the repo, install the service file, and restart it:

```
./deploy_to_inky.sh
```

## Watch and auto-deploy

Install the file watcher on macOS:

```
brew install fswatch
```

Then keep this running while you edit:

```
./watch_deploy.sh
```

Defaults: 2s debounce, ignores `.git`, `__pycache__`, `*.pyc`, `.DS_Store`, and `web/`.
