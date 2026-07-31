from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable

from .config import ConfigError, load_config
from .diff import diff_snapshots
from .models import AppConfig, JournalAccount, ManuscriptRecord, StatusSnapshot
from .notifier import create_notifier, format_changes_message, format_report_message
from .parsing.status_rules import is_terminal_status
from .storage import load_snapshot, save_snapshot


ScrapeFunc = Callable[[JournalAccount, AppConfig, bool], list[ManuscriptRecord]]
NotifyFunc = Callable[[str, str], None]


class _NotifierSender:
    def __init__(self, config: AppConfig) -> None:
        self._notifier = create_notifier(config)

    def __call__(self, title: str, body: str) -> None:
        result = self._notifier.send(title, body)
        if not result.ok:
            logging.error("Notification failed: %s", result.message)
            raise RuntimeError(result.message)

    def close(self) -> None:
        self._notifier.close()


def _setup_logging(config: AppConfig) -> None:
    config.log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=config.log_dir / "app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _default_scrape(journal: JournalAccount, config: AppConfig, debug: bool) -> list[ManuscriptRecord]:
    from .platforms.scholarone import ScholarOneScraper

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
        created_at=record.created_at,
        submitted_at=record.submitted_at,
        archived=is_terminal_status(record.status),
    )


def run_test_notification(
    config: AppConfig,
    notifier: NotifyFunc | None = None,
) -> int:
    _setup_logging(config)
    sender = notifier or _default_notifier(config)
    try:
        try:
            sender("IEEE ScholarOne Monitor Test", "Notification is configured.")
        except Exception:
            logging.exception("Notification test failed")
            return 1
    finally:
        close = getattr(sender, "close", None)
        if notifier is None and close is not None:
            close()
    return 0


def run_reauth(
    config: AppConfig,
    scraper: ScrapeFunc = _default_scrape,
    debug: bool = True,
) -> int:
    _setup_logging(config)
    logging.info("Starting manual browser session refresh")
    try:
        collect_records(config, scraper=scraper, debug=debug)
    except Exception:
        logging.exception("Manual browser session refresh failed")
        return 2
    logging.info("Finished manual browser session refresh")
    return 0


def _notify_scrape_failure(config: AppConfig, error: Exception, notifier: NotifyFunc | None) -> None:
    sender = notifier or _default_notifier(config)
    try:
        message = str(error)
        body = (
            "IEEE ScholarOne status check failed before a new snapshot could be saved.\n\n"
            f"Error: {message}\n\n"
            "The previous local status snapshot was kept unchanged.\n\n"
            "If this is a Cloudflare human verification, run:\n\n"
            ".\\.venv\\Scripts\\python.exe -m ieee_scholarone_monitor reauth"
        )
        sender("IEEE ScholarOne Monitor Needs Attention", body)
    finally:
        close = getattr(sender, "close", None)
        if notifier is None and close is not None:
            close()


def _send_notification_with_retries(
    sender: NotifyFunc,
    title: str,
    body: str,
    attempts: int = 3,
    delay_seconds: float = 1.0,
) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            sender(title, body)
            return
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            logging.warning(
                "Notification attempt %s/%s failed: %s",
                attempt,
                attempts,
                exc,
            )
            time.sleep(delay_seconds)
    assert last_error is not None
    raise last_error


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
    except Exception as exc:
        logging.exception("Status scrape failed")
        try:
            _notify_scrape_failure(config, exc, notifier)
        except Exception:
            logging.exception("Failure notification failed")
        return 2

    current = StatusSnapshot.from_records(records)
    previous = load_snapshot(config.status_path)
    changes = diff_snapshots(previous, current)
    save_snapshot(config.status_path, current)

    should_report = force_report or config.run_mode == "daily_report"
    if changes or should_report:
        title = "IEEE ScholarOne Review Status Notification"
        body = format_changes_message(changes) if changes and not should_report else format_report_message(records)
        sender = notifier or _default_notifier(config)
        try:
            try:
                _send_notification_with_retries(sender, title, body)
            except Exception:
                logging.exception("Notification failed")
                return 1
        finally:
            close = getattr(sender, "close", None)
            if notifier is None and close is not None:
                close()

    logging.info("Finished IEEE ScholarOne status check with %s change(s)", len(changes))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ieee-scholarone-monitor")
    parser.add_argument("--debug", action="store_true", help="Run browser visibly and save diagnostics")
    parser.add_argument("--dump", action="store_true", help="Save successful page HTML, screenshot, and table rows")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("test", help="Send a test notification")
    subparsers.add_parser("check", help="Run normal status check")
    subparsers.add_parser("report", help="Send current status report")
    subparsers.add_parser("reauth", help="Open a visible browser to refresh login/security verification")
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
        return run_check(config, debug=args.debug or args.dump)
    if args.command == "report":
        return run_check(config, debug=args.debug or args.dump, force_report=True)
    if args.command == "reauth":
        return run_reauth(config, debug=True)
    parser.error(f"Unsupported command: {args.command}")
    return 2
