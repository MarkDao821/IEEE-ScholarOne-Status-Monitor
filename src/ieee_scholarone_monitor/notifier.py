from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import html
import smtplib
from types import TracebackType
from typing import Callable

import httpx

from .models import AppConfig, ManuscriptRecord, StatusChange


PUSHPLUS_URL = "https://www.pushplus.plus/send"
SERVERCHAN_TURBO_URL_TEMPLATE = "https://sctapi.ftqq.com/{sendkey}.send"


@dataclass(frozen=True)
class NotificationResult:
    ok: bool
    message: str


def _redact_token(message: str, token: str) -> str:
    return message.replace(token, "[redacted]") if token else message


def _status_block(status: str) -> str:
    text = (status or "(unknown)").replace("```", "'''").strip()
    return f"```\n{text}\n```"


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


def _format_email_html(body: str) -> str:
    lines = body.splitlines()
    parts = [
        '<!doctype html>',
        '<html>',
        '<body style="margin:0;padding:18px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;line-height:1.5;">',
    ]
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped == "---":
            parts.append('<hr style="border:0;border-top:1px solid #d1d5db;margin:18px 0;">')
            index += 1
            continue
        if stripped == "```":
            status_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "```":
                status_lines.append(lines[index])
                index += 1
            status = "\n".join(status_lines).strip() or "(unknown)"
            escaped_status = "<br>".join(html.escape(item) for item in status.splitlines())
            parts.append(
                '<div style="margin:10px 0 14px 0;">'
                '<span style="display:inline-block;background-color:#fff3bf;border:1px solid #ffd43b;'
                'border-radius:6px;padding:6px 10px;font-weight:700;color:#5c3c00;">'
                f"{escaped_status}"
                "</span></div>"
            )
            if index < len(lines) and lines[index].strip() == "```":
                index += 1
            continue
        if ": " in line:
            label, value = line.split(": ", 1)
            parts.append(
                '<div style="margin:6px 0;">'
                f'<strong>{html.escape(label)}:</strong> {html.escape(value)}'
                "</div>"
            )
        else:
            parts.append(f'<div style="margin:6px 0;">{html.escape(line)}</div>')
        index += 1
    parts.append("</body></html>")
    return "".join(parts)


def format_changes_message(changes: list[StatusChange]) -> str:
    parts: list[str] = []
    for change in changes:
        parts.append(
            _join_fields(
                [
                    f"Journal: {change.journal_name}",
                    f"Change: {change.kind}",
                    f"Manuscript ID: {change.manuscript_id or '(unknown)'}",
                    f"Title: {change.title or '(unknown)'}",
                    f"Previous Status: {change.previous_status or '(none)'}",
                    _status_block(change.current_status),
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
        parts.append(
            _join_fields(
                [
                    f"Journal: {record.journal_name}",
                    f"Manuscript ID: {record.manuscript_id or '(unknown)'}",
                    f"Title: {record.title or '(unknown)'}",
                    _status_block(record.status),
                    f"Created: {record.created_at or '(unknown)'}",
                    f"Submitted: {record.submitted_at or '(unknown)'}",
                    f"Checked At: {_format_checked_at(record.checked_at)}",
                    f"Submission System: {record.url}",
                ]
            )
        )
    return "\n\n---\n\n".join(parts)


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


class EmailNotifier:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_address: str,
        to_addresses: tuple[str, ...],
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._to_addresses = to_addresses
        self._smtp_factory = smtp_factory

    def close(self) -> None:
        pass

    def __enter__(self) -> "EmailNotifier":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def send(self, title: str, body: str) -> NotificationResult:
        message = EmailMessage()
        message["Subject"] = title
        message["From"] = self._from_address
        message["To"] = ", ".join(self._to_addresses)
        message.set_content(body)
        message.add_alternative(_format_email_html(body), subtype="html")

        smtp = None
        try:
            smtp = self._smtp_factory(self._smtp_host, self._smtp_port, timeout=20)
            smtp.starttls()
            smtp.login(self._username, self._password)
            smtp.send_message(
                message,
                from_addr=self._from_address,
                to_addrs=list(self._to_addresses),
            )
        except (OSError, smtplib.SMTPException) as exc:
            return NotificationResult(
                ok=False,
                message=f"Email request failed: {_redact_token(str(exc), self._password)}",
            )
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except (OSError, smtplib.SMTPException):
                    pass
        return NotificationResult(True, "Email notification sent")


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


Notifier = PushPlusNotifier | ServerChanTurboNotifier | EmailNotifier


def create_notifier(provider: str | AppConfig, token: str = "") -> Notifier:
    if isinstance(provider, AppConfig):
        return create_notifier_from_config(provider)

    normalized = provider.strip().lower()
    if normalized == "pushplus":
        return PushPlusNotifier(token)
    if normalized in {"serverchan", "serverchan_turbo", "server_chan_turbo"}:
        return ServerChanTurboNotifier(token)
    raise ValueError(f"Unsupported WeChat provider: {provider}")


def create_notifier_from_config(config: AppConfig) -> Notifier:
    normalized = config.notify_provider.strip().lower()
    if normalized == "wechat":
        return create_notifier(config.wechat_provider, config.wechat_token)
    if normalized == "email":
        return EmailNotifier(
            smtp_host=config.email_smtp_host,
            smtp_port=config.email_smtp_port,
            username=config.email_username,
            password=config.email_password,
            from_address=config.email_from,
            to_addresses=config.email_to,
        )
    raise ValueError(f"Unsupported notification provider: {config.notify_provider}")
