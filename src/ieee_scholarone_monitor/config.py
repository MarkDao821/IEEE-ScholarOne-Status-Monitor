from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .models import AppConfig, JournalAccount


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
VALID_MODES = {"normal", "daily_report", "test"}
VALID_NOTIFY_PROVIDERS = {"wechat", "email"}


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


def _split_email_recipients(value: str) -> tuple[str, ...]:
    recipients = tuple(item.strip() for item in re.split(r"[,;]", value) if item.strip())
    if not recipients:
        raise ConfigError("Missing required configuration: EMAIL_TO")
    return recipients


def _as_int(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _as_nonnegative_int(value: str, name: str) -> int:
    number = _as_int(value, name)
    if number < 0:
        raise ConfigError(f"{name} must be zero or greater")
    return number


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

    notify_provider = os.getenv("NOTIFY_PROVIDER", "wechat").strip().lower() or "wechat"
    if notify_provider not in VALID_NOTIFY_PROVIDERS:
        raise ConfigError(
            f"NOTIFY_PROVIDER must be one of: {', '.join(sorted(VALID_NOTIFY_PROVIDERS))}"
        )

    provider = os.getenv("WECHAT_PROVIDER", "").strip()
    token = os.getenv("WECHAT_TOKEN", "").strip()
    email_smtp_host = os.getenv("EMAIL_SMTP_HOST", "").strip()
    email_smtp_port = _as_int(os.getenv("EMAIL_SMTP_PORT", "587").strip(), "EMAIL_SMTP_PORT")
    email_username = os.getenv("EMAIL_USERNAME", "").strip()
    email_password = os.getenv("EMAIL_PASSWORD", "").strip()
    email_from = os.getenv("EMAIL_FROM", "").strip()
    email_to = _split_email_recipients(os.getenv("EMAIL_TO", "")) if notify_provider == "email" else ()

    if notify_provider == "wechat":
        if not provider:
            raise ConfigError("Missing required configuration: WECHAT_PROVIDER")
        if not token:
            raise ConfigError("Missing required configuration: WECHAT_TOKEN")
    if notify_provider == "email":
        missing = [
            name
            for name, value in {
                "EMAIL_SMTP_HOST": email_smtp_host,
                "EMAIL_USERNAME": email_username,
                "EMAIL_PASSWORD": email_password,
                "EMAIL_FROM": email_from,
            }.items()
            if not value
        ]
        if missing:
            raise ConfigError(
                f"Missing required configuration: {', '.join(missing)}"
            )

    return AppConfig(
        journals=_load_journal_accounts(selected_journals_file),
        wechat_provider=provider,
        wechat_token=token,
        run_mode=run_mode,
        headless=_as_bool(os.getenv("HEADLESS"), True),
        status_path=Path(os.getenv("STATUS_PATH", "data/status.json")),
        log_dir=Path(os.getenv("LOG_DIR", "logs")),
        browser_profile_dir=Path(os.getenv("BROWSER_PROFILE_DIR", "data/browser-profile")),
        challenge_timeout_seconds=_as_nonnegative_int(
            os.getenv("CHALLENGE_TIMEOUT_SECONDS", "180").strip(),
            "CHALLENGE_TIMEOUT_SECONDS",
        ),
        notify_provider=notify_provider,
        email_smtp_host=email_smtp_host,
        email_smtp_port=email_smtp_port,
        email_username=email_username,
        email_password=email_password,
        email_from=email_from,
        email_to=email_to,
    )
