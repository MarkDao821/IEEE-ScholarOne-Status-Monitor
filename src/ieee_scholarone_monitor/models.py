from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_identity(value: str) -> str:
    return " ".join(value.strip().lower().split())


@dataclass(frozen=True)
class JournalAccount:
    key: str
    name: str
    platform: str
    url: str
    username: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class AppConfig:
    journals: tuple[JournalAccount, ...]
    wechat_provider: str
    wechat_token: str = field(repr=False)
    run_mode: str
    headless: bool
    status_path: Path
    log_dir: Path
    browser_profile_dir: Path = Path("data/browser-profile")
    challenge_timeout_seconds: int = 180
    notify_provider: str = "wechat"
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = field(default="", repr=False)
    email_from: str = ""
    email_to: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManuscriptRecord:
    journal_key: str
    journal_name: str
    manuscript_id: str
    title: str
    status: str
    url: str
    checked_at: str
    created_at: str = ""
    submitted_at: str = ""
    archived: bool = False

    @property
    def identity(self) -> str:
        return self.manuscript_id.strip() or normalize_identity(self.title)

    def to_dict(self) -> dict[str, Any]:
        return {
            "journal_key": self.journal_key,
            "journal_name": self.journal_name,
            "manuscript_id": self.manuscript_id,
            "title": self.title,
            "status": self.status,
            "url": self.url,
            "checked_at": self.checked_at,
            "created_at": self.created_at,
            "submitted_at": self.submitted_at,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManuscriptRecord":
        return cls(
            journal_key=str(data.get("journal_key", "")),
            journal_name=str(data.get("journal_name", "")),
            manuscript_id=str(data.get("manuscript_id", "")),
            title=str(data.get("title", "")),
            status=str(data.get("status", "")),
            url=str(data.get("url", "")),
            checked_at=str(data.get("checked_at", "")),
            created_at=str(data.get("created_at", "")),
            submitted_at=str(data.get("submitted_at", "")),
            archived=bool(data.get("archived", False)),
        )


@dataclass(frozen=True)
class StatusSnapshot:
    checked_at: str
    manuscripts: tuple[ManuscriptRecord, ...]

    @classmethod
    def from_records(cls, records: list[ManuscriptRecord]) -> "StatusSnapshot":
        return cls(checked_at=utc_now(), manuscripts=tuple(records))

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked_at": self.checked_at,
            "manuscripts": [record.to_dict() for record in self.manuscripts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StatusSnapshot":
        return cls(
            checked_at=str(data.get("checked_at", "")),
            manuscripts=tuple(
                ManuscriptRecord.from_dict(item)
                for item in data.get("manuscripts", [])
            ),
        )


@dataclass(frozen=True)
class StatusChange:
    kind: str
    journal_key: str
    journal_name: str
    manuscript_id: str
    title: str
    previous_status: str
    current_status: str
    checked_at: str
    url: str
    created_at: str = ""
    submitted_at: str = ""
