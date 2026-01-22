# Codex Rules for Inky Project

## 1) SSH Connection
- Host alias: `inky` (from `~/.ssh/config`)
- Example:
  - `ssh inky`
- Overrides:
  - `INKY_HOST` can override the SSH host (e.g. `INKY_HOST=192.168.2.109`).
  - `RSYNC_SSH_OPTS` can override SSH options (default: `-o StrictHostKeyChecking=accept-new`).

## 2) Execute Script
- Dashboard script:
  - `/home/hazam/projects/my-dashboard/my_dashboard.py`
- Run command:
  - `/home/hazam/inky-venv/bin/python /home/hazam/projects/my-dashboard/my_dashboard.py`
- Example:
  - `ssh inky '/home/hazam/inky-venv/bin/python /home/hazam/projects/my-dashboard/my_dashboard.py'`

## 3) Cron Tasks
- Current schedule:
  - `*/15 * * * * /home/hazam/inky-venv/bin/python /home/hazam/projects/my-dashboard/my_dashboard.py`
- Check cron:
  - `ssh inky 'crontab -l'`
- Edit cron:
  - `ssh inky 'crontab -e'`

## 4) Server Startup
- Systemd service:
  - `my-dashboard-http.service`
- Exec:
  - `/home/hazam/inky-venv/bin/python /home/hazam/projects/my-dashboard/server.py --port 80`
- Status:
  - `ssh inky 'systemctl status my-dashboard-http.service --no-pager'`
- Restart:
  - `ssh inky 'sudo systemctl restart my-dashboard-http.service'`
