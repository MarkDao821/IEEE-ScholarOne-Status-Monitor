from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import TracebackType

import httpx

from .models import ManuscriptRecord, StatusChange


PUSHPLUS_URL = "https://www.pushplus.plus/send"
SERVERCHAN_TURBO_URL_TEMPLATE = "https://sctapi.ftqq.com/{sendkey}.send"


@dataclass(frozen=True)
class NotificationResult:
    ok: bool
    message: str


def _redact_token(message: str, token: str) -> str:
    return message.replace(token, "[redacted]") if token else message


def _highlight(value: str) -> str:
    text = (value or "(unknown)").replace("`", "'").strip()
    return f"`{text}`"


def _format_checked_at(value: str) -> str:
    if not value:
        return "(unknown)"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone(timedelta(hours=8)))
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _join_fields(lines: list[str]) -> str:
    return "\n\n".join(lines)


def format_changes_message(changes: list[StatusChange]) -> str:
    parts: list[str] = []
    for change in changes:
        parts.append(
            _join_fields(
                [
                    f"Journal: {change.journal_name}",
                    f"Change: {change.kind}",
                    f"Manuscript ID: {change.manuscript_id or '(unknown)'}",
                    f"**Title:** {change.title or '(unknown)'}",
                    f"Previous Status: {change.previous_status or '(none)'}",
                    f"**Current Status:** {_highlight(change.current_status)}",
                    f"Created: {change.created_at or '(unknown)'}",
                    f"Submitted: {change.submitted_at or '(unknown)'}",
                    f"Checked At: {_format_checked_at(change.checked_at)}",
                    f"Submission System: {change.url}",
                ]
            )
        )
    return "\n\n---\n\n".join(parts)


def format_report_message(records: list[ManuscriptRecord]) -> str:
    if not records:
        return "No active manuscripts found."
    parts: list[str] = []
    for record in records:
        if record.archived:
            continue
        parts.append(
            _join_fields(
                [
                    f"Journal: {record.journal_name}",
                    f"Manuscript ID: {record.manuscript_id or '(unknown)'}",
                    f"**Title:** {record.title or '(unknown)'}",
                    f"**Current Status:** {_highlight(record.status)}",
                    f"Created: {record.created_at or '(unknown)'}",
                    f"Submitted: {record.submitted_at or '(unknown)'}",
                    f"Checked At: {_format_checked_at(record.checked_at)}",
                    f"Submission System: {record.url}",
                ]
            )
        )
    return "\n\n---\n\n".join(parts) if parts else "No active manuscripts found."


class PushPlusNotifier:
    def __init__(self, token: str, client: httpx.Client | None = None) -> None:
        self._token = token
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=20)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PushPlusNotifier":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def send(self, title: str, body: str) -> NotificationResult:
        try:
            response = self._client.post(
                PUSHPLUS_URL,
                json={
                    "token": self._token,
                    "title": title,
                    "content": body,
                    "template": "markdown",
                },
            )
        except httpx.HTTPError as exc:
            return NotificationResult(
                ok=False,
                message=f"PushPlus request failed: {_redact_token(str(exc), self._token)}",
            )
        return _pushplus_result(response, self._token)


class ServerChanTurboNotifier:
    def __init__(self, sendkey: str, client: httpx.Client | None = None) -> None:
        self._sendkey = sendkey
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=20)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "ServerChanTurboNotifier":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def send(self, title: str, body: str) -> NotificationResult:
        url = SERVERCHAN_TURBO_URL_TEMPLATE.format(sendkey=self._sendkey)
        try:
            response = self._client.post(url, data={"title": title, "desp": body})
        except httpx.HTTPError as exc:
            return NotificationResult(
                ok=False,
                message=f"Server Chan request failed: {_redact_token(str(exc), self._sendkey)}",
            )
        return _serverchan_result(response, self._sendkey)


def _pushplus_result(response: httpx.Response, token: str) -> NotificationResult:
    if response.status_code >= 400:
        return NotificationResult(False, f"PushPlus request failed with HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        return NotificationResult(False, "PushPlus returned invalid JSON")
    if isinstance(payload, dict) and payload.get("code") in {200, "200"}:
        return NotificationResult(True, "PushPlus notification sent")
    message = str(payload.get("msg", "unknown provider error")) if isinstance(payload, dict) else "unexpected JSON shape"
    return NotificationResult(False, f"PushPlus rejected notification: {_redact_token(message, token)}")


def _serverchan_result(response: httpx.Response, token: str) -> NotificationResult:
    if response.status_code >= 400:
        return NotificationResult(False, f"Server Chan request failed with HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        return NotificationResult(False, "Server Chan returned invalid JSON")
    if isinstance(payload, dict) and payload.get("code") in {0, "0"}:
        return NotificationResult(True, "Server Chan notification sent")
    message = str(payload.get("message", payload.get("msg", "unknown provider error"))) if isinstance(payload, dict) else "unexpected JSON shape"
    return NotificationResult(False, f"Server Chan rejected notification: {_redact_token(message, token)}")


Notifier = PushPlusNotifier | ServerChanTurboNotifier


def create_notifier(provider: str, token: str) -> Notifier:
    normalized = provider.strip().lower()
    if normalized == "pushplus":
        return PushPlusNotifier(token)
    if normalized in {"serverchan", "serverchan_turbo", "server_chan_turbo"}:
        return ServerChanTurboNotifier(token)
    raise ValueError(f"Unsupported WeChat provider: {provider}")
