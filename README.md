# IEEE ScholarOne Status Monitor

Configurable local monitor for IEEE journals that use ScholarOne / Manuscript Central.
It logs in, reads manuscript status rows, stores the latest snapshot locally, and sends
WeChat notifications through Server Chan Turbo or PushPlus.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item .env.example .env
Copy-Item journals.example.toml journals.toml
```

If Playwright Chromium is not installed, the scraper falls back to system Microsoft Edge.

## Configuration

Edit `journals.toml`:

```toml
[[journals]]
key = "ieee-tcyb"
name = "IEEE TCYB"
platform = "scholarone"
url = "https://mc.manuscriptcentral.com/cyb-ieee"
username_env = "TCYB_USERNAME"
password_env = "TCYB_PASSWORD"
```

Edit `.env`:

```dotenv
WECHAT_PROVIDER=serverchan
WECHAT_TOKEN=your_server_chan_send_key
RUN_MODE=normal
TCYB_USERNAME=your_scholarone_username
TCYB_PASSWORD=your_scholarone_password
```

To add another IEEE ScholarOne journal, add another `[[journals]]` entry and point
`username_env` / `password_env` at different environment variable names.

## Commands

Test WeChat notification:

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor test
```

Run normal status check. This sends a message only when a baseline or status change is detected:

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor check
```

Send a current status report regardless of changes:

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor report
```

Run visibly for login/debugging:

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor --debug check
```

Save successful page diagnostics without changing the normal workflow:

```powershell
.\.venv\Scripts\python.exe run_monitor.py --dump report
```

This writes a screenshot, redacted HTML, and parsed table rows under `logs/dumps`.

## Runtime Files

- `.env`: local secrets and behavior switches. Do not commit it.
- `journals.toml`: local journal list. Commit only if it does not include secrets.
- `data/status.json`: latest known manuscript snapshot.
- `logs/app.log`: status check logs.
- `logs/screenshots` and `logs/pages`: failure diagnostics with login fields redacted.

## Scheduling

See `docs/windows-task-scheduler.md` for Windows Task Scheduler commands.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
