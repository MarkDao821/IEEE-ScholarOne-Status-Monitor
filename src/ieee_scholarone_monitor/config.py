from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .models import AppConfig, JournalAccount


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
VALID_MODES = {"normal", "daily_report", "test"}


class ConfigError(ValueError):
    pass


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in TRUE_VALUES


def _require_env(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _load_journal_accounts(path: Path) -> tuple[JournalAccount, ...]:
    if not path.exists():
        raise ConfigError(f"Journals file does not exist: {path}")

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    items = data.get("journals", [])
    if not isinstance(items, list) or not items:
        raise ConfigError("Journals file must contain at least one [[journals]] entry")

    journals: list[JournalAccount] = []
    for index, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            raise ConfigError(f"Journal entry #{index} must be a table")
        journal = _journal_from_dict(raw, index)
        if journal.platform.strip().lower() != "scholarone":
            raise ConfigError(f"Unsupported platform for {journal.name}: {journal.platform}")
        journals.append(journal)
    return tuple(journals)


def _journal_from_dict(raw: dict[str, Any], index: int) -> JournalAccount:
    required = ["key", "name", "platform", "url", "username_env", "password_env"]
    missing = [name for name in required if not str(raw.get(name, "")).strip()]
    if missing:
        raise ConfigError(
            f"Journal entry #{index} is missing required field(s): {', '.join(missing)}"
        )

    username_env = str(raw["username_env"]).strip()
    password_env = str(raw["password_env"]).strip()
    return JournalAccount(
        key=str(raw["key"]).strip(),
        name=str(raw["name"]).strip(),
        platform=str(raw["platform"]).strip(),
        url=str(raw["url"]).strip(),
        username=_require_env(username_env),
        password=_require_env(password_env),
    )


def load_config(
    env_file: str | Path | None = ".env",
    journals_file: str | Path | None = None,
) -> AppConfig:
    if env_file is not None:
        load_dotenv(env_file)

    selected_journals_file = Path(
        journals_file or os.getenv("JOURNALS_FILE", "journals.toml")
    )
    run_mode = os.getenv("RUN_MODE", "normal").strip().lower()
    if run_mode not in VALID_MODES:
        raise ConfigError(f"RUN_MODE must be one of: {', '.join(sorted(VALID_MODES))}")

    provider = os.getenv("WECHAT_PROVIDER", "").strip()
    token = os.getenv("WECHAT_TOKEN", "").strip()
    if not provider:
        raise ConfigError("Missing required configuration: WECHAT_PROVIDER")
    if not token:
        raise ConfigError("Missing required configuration: WECHAT_TOKEN")

    return AppConfig(
        journals=_load_journal_accounts(selected_journals_file),
        wechat_provider=provider,
        wechat_token=token,
        run_mode=run_mode,
        headless=_as_bool(os.getenv("HEADLESS"), True),
        status_path=Path(os.getenv("STATUS_PATH", "data/status.json")),
        log_dir=Path(os.getenv("LOG_DIR", "logs")),
    )
