from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import (
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from ..models import AppConfig, JournalAccount, ManuscriptRecord
from ..parsing.table_parser import parse_table_rows


LOGIN_SUBMIT_SCRIPT = """
() => {
    const form = document.forms[0];
    if (!form) {
        throw new Error("ScholarOne login form was not found");
    }
    const nextPage = typeof homePage !== "undefined" ? homePage : "HOME";
    if (typeof setField === "function" && typeof loginAction !== "undefined") {
        setField("XIK_PREACT", loginAction);
    } else if (form.XIK_PREACT && typeof loginAction !== "undefined") {
        form.XIK_PREACT.value = loginAction;
    }
    if (typeof setNextPage === "function") {
        setNextPage(nextPage);
    } else if (form.NEXT_PAGE) {
        form.NEXT_PAGE.value = nextPage;
    }
    form.submit();
}
"""


class ScrapeError(RuntimeError):
    pass


class SecurityChallengeRequired(ScrapeError):
    pass


class ScholarOneScraper:
    def scrape(
        self,
        journal: JournalAccount,
        config: AppConfig,
        debug: bool = False,
    ) -> list[ManuscriptRecord]:
        headless = config.headless and not debug
        with sync_playwright() as playwright:
            context = _launch_browser_context(
                playwright.chromium,
                config.browser_profile_dir / _safe_path_segment(journal.key),
                headless=headless,
            )
            page = context.pages[0] if context.pages else context.new_page()
            try:
                page.goto(journal.url, wait_until="domcontentloaded", timeout=60000)
                _wait_for_security_challenge(
                    page,
                    headless=headless,
                    timeout_seconds=config.challenge_timeout_seconds,
                )
                _fill_login(page, journal.username, journal.password)
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                _wait_for_security_challenge(
                    page,
                    headless=headless,
                    timeout_seconds=config.challenge_timeout_seconds,
                )
                if page.locator("input[type='password']").first.is_visible(timeout=3000):
                    raise ScrapeError(f"ScholarOne login appears to have failed for {journal.name}")
                _go_to_author_area(page)
                rows = _extract_table_rows(page)
                if debug:
                    _save_debug_dump(
                        page,
                        rows,
                        config.log_dir,
                        journal.key,
                        (journal.username, journal.password),
                    )
                records = parse_table_rows(journal, rows, page.url)
                if not records:
                    raise ScrapeError(f"No manuscript status rows found for {journal.name}")
                return records
            except Exception as exc:
                _save_failure_artifacts(
                    page,
                    config.log_dir,
                    (journal.username, journal.password),
                )
                if isinstance(exc, ScrapeError):
                    raise
                raise ScrapeError(f"ScholarOne scrape failed for {journal.name}: {exc}") from exc
            finally:
                context.close()


def _launch_browser_context(chromium, user_data_dir: Path, headless: bool):
    user_data_dir.mkdir(parents=True, exist_ok=True)
    try:
        return chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
        )
    except PlaywrightError as exc:
        if "Executable doesn't exist" not in str(exc):
            raise
        return chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            channel="msedge",
            headless=headless,
        )


def _safe_path_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "journal"


def _wait_for_security_challenge(
    page: Page,
    headless: bool,
    timeout_seconds: int,
) -> None:
    if not _security_challenge_present(page):
        return
    if headless:
        raise SecurityChallengeRequired(
            "Cloudflare human verification is required. Run "
            "'.\\.venv\\Scripts\\python.exe -m ieee_scholarone_monitor reauth' "
            "to refresh the saved browser session."
        )

    deadline = datetime.now(timezone.utc).timestamp() + timeout_seconds
    while _security_challenge_present(page):
        if datetime.now(timezone.utc).timestamp() >= deadline:
            raise SecurityChallengeRequired(
                "Timed out waiting for Cloudflare human verification. "
                "Complete the visible challenge or increase CHALLENGE_TIMEOUT_SECONDS."
            )
        page.wait_for_timeout(1000)
    page.wait_for_load_state("domcontentloaded", timeout=60000)


def _security_challenge_present(page: Page) -> bool:
    try:
        if page.locator(
            "iframe[src*='challenges.cloudflare.com'], "
            "input[name='cf-turnstile-response'], "
            ".cf-turnstile"
        ).count():
            return True
        content = page.content().lower()
    except PlaywrightError:
        return False
    markers = (
        "正在进行安全验证",
        "请验证您是真人",
        "verifying you are human",
        "checking if the site connection is secure",
        "challenge-platform",
        "cloudflare ray id",
    )
    return any(marker in content for marker in markers)


def _fill_login(page: Page, username: str, password: str) -> None:
    username_box = page.locator(
        "input[name='USERID'], input[name='userId'], input[name='login'], input[type='email'], input[type='text']"
    ).first
    password_box = page.locator(
        "input[name='PASSWORD'], input[name='password'], input[type='password']"
    ).first
    username_box.fill(username)
    password_box.fill(password)
    if page.locator("#logInButton").first.is_visible(timeout=5000):
        with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
            page.evaluate(LOGIN_SUBMIT_SCRIPT)
        return
    if page.locator("button[type='submit'], input[type='submit']").first.is_visible(timeout=5000):
        with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
            page.locator("button[type='submit'], input[type='submit']").first.click()
        return
    password_box.press("Enter")


def _go_to_author_area(page: Page) -> None:
    candidates = [
        page.get_by_role("link", name="Author Center"),
        page.get_by_role("link", name="Author", exact=True),
        page.locator("a:has-text('Author Center')"),
        page.locator("a:has-text('Author')"),
    ]
    for candidate in candidates:
        try:
            if candidate.first.is_visible(timeout=3000):
                candidate.first.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                return
        except PlaywrightTimeoutError:
            continue
    if "Author" not in page.content():
        raise ScrapeError("Could not locate Author Center link after login")


def _extract_table_rows(page: Page) -> list[list[str]]:
    rows = page.locator("table tr").all()
    extracted: list[list[str]] = []
    for row in rows:
        cells = [cell.inner_text().strip() for cell in row.locator("th, td").all()]
        if cells:
            extracted.append(cells)
    return extracted


def _artifact_paths(log_dir: Path) -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    suffix = uuid4().hex[:8]
    screenshots = log_dir / "screenshots"
    pages = log_dir / "pages"
    screenshots.mkdir(parents=True, exist_ok=True)
    pages.mkdir(parents=True, exist_ok=True)
    return (
        screenshots / f"failure-{stamp}-{suffix}.png",
        pages / f"failure-{stamp}-{suffix}.html",
    )


def _debug_dump_paths(log_dir: Path, journal_key: str) -> tuple[Path, Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    suffix = uuid4().hex[:8]
    dumps = log_dir / "dumps"
    dumps.mkdir(parents=True, exist_ok=True)
    safe_key = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in journal_key)
    base = f"{safe_key}-{stamp}-{suffix}"
    return (
        dumps / f"{base}.png",
        dumps / f"{base}.html",
        dumps / f"{base}.rows.json",
    )


def _save_debug_dump(
    page: Page,
    rows: list[list[str]],
    log_dir: Path,
    journal_key: str,
    secrets: tuple[str, ...],
) -> None:
    screenshot_path, html_path, rows_path = _debug_dump_paths(log_dir, journal_key)
    _clear_sensitive_inputs(page)
    page.screenshot(path=str(screenshot_path), full_page=True)
    html = page.content()
    for secret in secrets:
        if secret:
            html = html.replace(secret, "[redacted]")
    html_path.write_text(html, encoding="utf-8")
    rows_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _save_failure_artifacts(page: Page, log_dir: Path, secrets: tuple[str, ...]) -> None:
    screenshot_path, html_path = _artifact_paths(log_dir)
    _clear_sensitive_inputs(page)
    page.screenshot(path=str(screenshot_path), full_page=True)
    html = page.content()
    for secret in secrets:
        if secret:
            html = html.replace(secret, "[redacted]")
    html_path.write_text(html, encoding="utf-8")


def _clear_sensitive_inputs(page: Page) -> None:
    page.locator("input[type='password']").evaluate_all(
        "(inputs) => inputs.forEach((input) => { input.value = ''; })"
    )
    page.locator("input[type='text'], input[type='email']").evaluate_all(
        "(inputs) => inputs.forEach((input) => { input.value = ''; })"
    )
