from __future__ import annotations

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


class ScholarOneScraper:
    def scrape(
        self,
        journal: JournalAccount,
        config: AppConfig,
        debug: bool = False,
    ) -> list[ManuscriptRecord]:
        headless = config.headless and not debug
        with sync_playwright() as playwright:
            browser = _launch_browser(playwright.chromium, headless=headless)
            page = browser.new_page()
            try:
                page.goto(journal.url, wait_until="domcontentloaded", timeout=60000)
                _fill_login(page, journal.username, journal.password)
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                if page.locator("input[type='password']").first.is_visible(timeout=3000):
                    raise ScrapeError(f"ScholarOne login appears to have failed for {journal.name}")
                _go_to_author_area(page)
                rows = _extract_table_rows(page)
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
                browser.close()


def _launch_browser(chromium, headless: bool):
    try:
        return chromium.launch(headless=headless)
    except PlaywrightError as exc:
        if "Executable doesn't exist" not in str(exc):
            raise
        return chromium.launch(channel="msedge", headless=headless)


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
