"""测试命令行主流程。

测试什么：
- 第一次检查时是否发送 baseline 通知。
- 状态没有变化时 normal 模式是否不重复通知。
- daily_report 模式是否每次都发送当前状态报告。
- 测试通知命令是否能发送探测消息。

需要填写什么：
- 不需要填写真实 ScholarOne 账号或真实通知配置。
- _config() 和 _scraper() 都使用合成数据，notifier 也只是把消息存进列表。
"""

from pathlib import Path

import pytest

from ieee_scholarone_monitor.cli import (
    _send_notification_with_retries,
    run_check,
    run_test_notification,
)
from ieee_scholarone_monitor.models import AppConfig, JournalAccount, ManuscriptRecord


def _config(tmp_path: Path, mode: str = "normal") -> AppConfig:
    return AppConfig(
        journals=(
            JournalAccount(
                key="ieee-tcyb",
                name="IEEE TCYB",
                platform="scholarone",
                url="https://example.test",
                username="alice",
                password="secret",
            ),
        ),
        wechat_provider="serverchan",
        wechat_token="send-key",
        run_mode=mode,
        headless=True,
        status_path=tmp_path / "status.json",
        log_dir=tmp_path / "logs",
    )


def _scraper(journal, config, debug):
    return [
        ManuscriptRecord(
            journal_key=journal.key,
            journal_name=journal.name,
            manuscript_id="TCYB-2026-001",
            title="A Paper",
            status="Under Review",
            url=journal.url,
            checked_at="2026-05-25T00:00:00+00:00",
        )
    ]


def test_run_check_sends_baseline_then_suppresses_unchanged(tmp_path):
    sent = []

    def notifier(title: str, body: str):
        sent.append((title, body))

    config = _config(tmp_path)

    assert run_check(config, scraper=_scraper, notifier=notifier) == 0
    assert run_check(config, scraper=_scraper, notifier=notifier) == 0

    assert len(sent) == 1
    assert sent[0][0] == "IEEE ScholarOne Review Status Notification"
    assert "Under Review" in sent[0][1]


def test_report_mode_sends_current_status_even_when_unchanged(tmp_path):
    sent = []

    def notifier(title: str, body: str):
        sent.append((title, body))

    config = _config(tmp_path, mode="daily_report")

    assert run_check(config, scraper=_scraper, notifier=notifier) == 0
    sent.clear()
    assert run_check(config, scraper=_scraper, notifier=notifier) == 0

    assert len(sent) == 1
    assert sent[0][0] == "IEEE ScholarOne Review Status Notification"
    assert "A Paper" in sent[0][1]
    assert "Under Review" in sent[0][1]


def test_run_test_notification_sends_probe(tmp_path):
    sent = []

    def notifier(title: str, body: str):
        sent.append((title, body))

    assert run_test_notification(_config(tmp_path), notifier=notifier) == 0

    assert sent == [("IEEE ScholarOne Monitor Test", "Notification is configured.")]


def test_send_notification_with_retries_succeeds_after_transient_failure(monkeypatch):
    monkeypatch.setattr("ieee_scholarone_monitor.cli.time.sleep", lambda *_: None)
    calls: list[tuple[str, str]] = []

    def flaky_notifier(title: str, body: str):
        calls.append((title, body))
        if len(calls) == 1:
            raise RuntimeError("temporary failure")

    _send_notification_with_retries(flaky_notifier, "Title", "Body", attempts=3, delay_seconds=0)

    assert calls == [("Title", "Body"), ("Title", "Body")]


def test_send_notification_with_retries_raises_after_all_attempts(monkeypatch):
    monkeypatch.setattr("ieee_scholarone_monitor.cli.time.sleep", lambda *_: None)

    def always_fails(_title: str, _body: str):
        raise RuntimeError("still failing")

    with pytest.raises(RuntimeError, match="still failing"):
        _send_notification_with_retries(always_fails, "Title", "Body", attempts=2, delay_seconds=0)
