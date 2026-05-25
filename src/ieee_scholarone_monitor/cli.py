from __future__ import annotations

import argparse
import logging
from collections.abc import Callable

from .config import ConfigError, load_config
from .diff import diff_snapshots
from .models import AppConfig, JournalAccount, ManuscriptRecord, StatusSnapshot
from .notifier import create_notifier, format_changes_message, format_report_message
from .parsing.status_rules import is_terminal_status
from .platforms.scholarone import ScholarOneScraper
from .storage import load_snapshot, save_snapshot


ScrapeFunc = Callable[[JournalAccount, AppConfig, bool], list[ManuscriptRecord]]
NotifyFunc = Callable[[str, str], None]


class _NotifierSender:
    def __init__(self, config: AppConfig) -> None:
        self._notifier = create_notifier(config.wechat_provider, config.wechat_token)

    def __call__(self, title: str, body: str) -> None:
        result = self._notifier.send(title, body)
        if not result.ok:
            logging.error("Notification failed: %s", result.message)

    def close(self) -> None:
        self._notifier.close()


def _setup_logging(config: AppConfig) -> None:
    config.log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=config.log_dir / "app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def _default_scrape(journal: JournalAccount, config: AppConfig, debug: bool) -> list[ManuscriptRecord]:
    return ScholarOneScraper().scrape(journal, config, debug=debug)


def _default_notifier(config: AppConfig) -> NotifyFunc:
    return _NotifierSender(config)


def collect_records(
    config: AppConfig,
    scraper: ScrapeFunc = _default_scrape,
    debug: bool = False,
) -> list[ManuscriptRecord]:
    records: list[ManuscriptRecord] = []
    for journal in config.journals:
        records.extend(scraper(journal, config, debug))
    return [_with_archive_flag(record) for record in records]


def _with_archive_flag(record: ManuscriptRecord) -> ManuscriptRecord:
    if record.archived == is_terminal_status(record.status):
        return record
    return ManuscriptRecord(
        journal_key=record.journal_key,
        journal_name=record.journal_name,
        manuscript_id=record.manuscript_id,
        title=record.title,
        status=record.status,
        url=record.url,
        checked_at=record.checked_at,
        archived=is_terminal_status(record.status),
    )


def run_test_notification(
    config: AppConfig,
    notifier: NotifyFunc | None = None,
) -> int:
    _setup_logging(config)
    sender = notifier or _default_notifier(config)
    try:
        sender("IEEE ScholarOne Monitor Test", "WeChat notification is configured.")
    finally:
        close = getattr(sender, "close", None)
        if notifier is None and close is not None:
            close()
    return 0


def run_check(
    config: AppConfig,
    scraper: ScrapeFunc = _default_scrape,
    notifier: NotifyFunc | None = None,
    debug: bool = False,
    force_report: bool = False,
) -> int:
    _setup_logging(config)
    logging.info("Starting IEEE ScholarOne status check")
    try:
        records = collect_records(config, scraper=scraper, debug=debug)
    except Exception:
        logging.exception("Status scrape failed")
        return 2

    current = StatusSnapshot.from_records(records)
    previous = load_snapshot(config.status_path)
    changes = diff_snapshots(previous, current)
    save_snapshot(config.status_path, current)

    should_report = force_report or config.run_mode == "daily_report"
    if changes or should_report:
        title = "IEEE ScholarOne Review Status Update"
        body = format_changes_message(changes) if changes and not should_report else format_report_message(records)
        sender = notifier or _default_notifier(config)
        try:
            sender(title, body)
        finally:
            close = getattr(sender, "close", None)
            if notifier is None and close is not None:
                close()

    logging.info("Finished IEEE ScholarOne status check with %s change(s)", len(changes))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ieee-scholarone-monitor")
    parser.add_argument("--debug", action="store_true", help="Run browser visibly and save diagnostics")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("test", help="Send a WeChat test notification")
    subparsers.add_parser("check", help="Run normal status check")
    subparsers.add_parser("report", help="Send current status report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config()
    except ConfigError as exc:
        parser.error(str(exc))

    if args.command == "test":
        return run_test_notification(config)
    if args.command == "check":
        return run_check(config, debug=args.debug)
    if args.command == "report":
        return run_check(config, debug=args.debug, force_report=True)
    parser.error(f"Unsupported command: {args.command}")
    return 2
