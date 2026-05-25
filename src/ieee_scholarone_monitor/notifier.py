from __future__ import annotations

from dataclasses import dataclass
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


def format_changes_message(changes: list[StatusChange]) -> str:
    parts: list[str] = []
    for change in changes:
        parts.append(
            "\n".join(
                [
                    f"Journal: {change.journal_name}",
                    f"Change: {change.kind}",
                    f"Manuscript ID: {change.manuscript_id or '(unknown)'}",
                    f"Title: {change.title or '(unknown)'}",
                    f"Previous Status: {change.previous_status or '(none)'}",
                    f"Current Status: {change.current_status or '(none)'}",
                    f"Checked At: {change.checked_at}",
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
            "\n".join(
                [
                    f"Journal: {record.journal_name}",
                    f"Manuscript ID: {record.manuscript_id or '(unknown)'}",
                    f"Title: {record.title or '(unknown)'}",
                    f"Current Status: {record.status or '(unknown)'}",
                    f"Checked At: {record.checked_at}",
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
