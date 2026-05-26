from __future__ import annotations

import re

from ..models import JournalAccount, ManuscriptRecord, utc_now
from .status_rules import clean_text, has_status_signal, identity_title, is_terminal_status, looks_like_date_token, normalize_title, status_score


def parse_table_rows(
    journal: JournalAccount,
    rows: list[list[str]],
    page_url: str,
    checked_at: str | None = None,
) -> list[ManuscriptRecord]:
    checked = checked_at or utc_now()
    records_by_key: dict[str, ManuscriptRecord] = {}
    headers: list[str] | None = None

    for raw_cells in rows:
        cells = [clean_text(cell) for cell in raw_cells if clean_text(cell)]
        if len(cells) < 2:
            continue
        if _is_header_row(cells):
            headers = [cell.strip().lower() for cell in cells]
            continue

        header_record = _record_from_headers(journal, headers, cells, page_url, checked)
        if header_record is not None:
            existing = records_by_key.get(header_record.identity)
            records_by_key[header_record.identity] = (
                _prefer_record(existing, header_record) if existing else header_record
            )
            continue

        joined = " | ".join(cells)
        if _looks_like_navigation_row(joined):
            continue
        if not has_status_signal(joined):
            continue

        status = _pick_status(raw_cells, cells)
        title = _pick_title(cells, status)
        manuscript_id = _pick_manuscript_id(cells)
        if not _looks_like_manuscript_row(cells, manuscript_id, title, status):
            continue

        record = ManuscriptRecord(
            journal_key=journal.key,
            journal_name=journal.name,
            manuscript_id=manuscript_id,
            title=title or "Untitled manuscript",
            status=status or "Unknown",
            url=page_url or journal.url,
            checked_at=checked,
            archived=is_terminal_status(status),
        )
        key = record.identity
        existing = records_by_key.get(key)
        records_by_key[key] = _prefer_record(existing, record) if existing else record

    return list(records_by_key.values())


def _is_header_row(cells: list[str]) -> bool:
    normalized = {cell.strip().lower() for cell in cells}
    return {"status", "id", "title"}.issubset(normalized)


def _record_from_headers(
    journal: JournalAccount,
    headers: list[str] | None,
    cells: list[str],
    page_url: str,
    checked_at: str,
) -> ManuscriptRecord | None:
    if not headers:
        return None

    offset = max(0, len(cells) - len(headers))

    def field(*names: str) -> str:
        for name in names:
            if name in headers:
                index = headers.index(name) + offset
                if 0 <= index < len(cells):
                    return cells[index]
        return ""

    status_cell = field("status")
    id_cell = field("id", "manuscript id", "manuscript")
    title_cell = field("title")
    created_cell = field("created")
    submitted_cell = field("submitted")
    status = _pick_status([status_cell], [status_cell]) or _pick_status(cells, cells)
    manuscript_id = _pick_manuscript_id([id_cell]) or _pick_manuscript_id(cells)
    title = normalize_title(title_cell) or _pick_title(cells, status)
    if not _looks_like_manuscript_row(cells, manuscript_id, title, status):
        return None

    return ManuscriptRecord(
        journal_key=journal.key,
        journal_name=journal.name,
        manuscript_id=manuscript_id,
        title=title or "Untitled manuscript",
        status=status or "Unknown",
        url=page_url or journal.url,
        checked_at=checked_at,
        created_at=created_cell,
        submitted_at=submitted_cell,
        archived=is_terminal_status(status),
    )


def _looks_like_navigation_row(value: str) -> bool:
    lowered = value.lower()
    blocked = ("logout", "log out", "help", "instructions", "privacy", "terms", "search")
    return any(token in lowered for token in blocked)


def _looks_like_manuscript_row(
    cells: list[str],
    manuscript_id: str,
    title: str,
    status: str,
) -> bool:
    return bool((manuscript_id or len(title) > 16) and (status or has_status_signal(" ".join(cells))))


def _pick_manuscript_id(cells: list[str]) -> str:
    patterns = [
        r"\b\d{2}-[A-Z]{1,10}-\d{2,}[-_A-Z0-9]*\b",
        r"\b[A-Z]{2,10}-[A-Z]-\d{4}-\d{1,2}-\d{2,}\b",
        r"\b[A-Z]{2,10}[-_ ]?\d{2,}[-_A-Z0-9]*\b",
    ]
    for cell in cells:
        for pattern in patterns:
            match = re.search(pattern, cell, flags=re.IGNORECASE)
            if match and not looks_like_date_token(match.group(0)):
                return match.group(0)
    return ""


def _pick_status(raw_cells: list[str], cells: list[str]) -> str:
    line_candidates: list[str] = []
    for raw in raw_cells:
        lines = [clean_text(line) for line in raw.splitlines() if clean_text(line)]
        for line in lines:
            line = re.sub(r"^(current\s+)?status\s*:?\s*", "", line, flags=re.IGNORECASE)
            if has_status_signal(line) and not _is_action_text(line):
                line_candidates.append(line)
        if line_candidates:
            return line_candidates[0]

    scored = [(status_score(cell), len(cell), cell) for cell in cells if len(cell) <= 160]
    scored = [item for item in scored if item[0] > 0]
    if not scored:
        return ""
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][2]


def _pick_title(cells: list[str], status: str) -> str:
    candidates: list[str] = []
    status_lower = status.lower().strip()
    for cell in cells:
        title = normalize_title(cell)
        lowered = title.lower()
        if not title or lowered == status_lower:
            continue
        if _is_internal_identifier_block(title):
            continue
        if _looks_like_identifier(title):
            continue
        if has_status_signal(title):
            continue
        if len(title) > 16:
            candidates.append(title)
    if candidates:
        return max(candidates, key=len)
    return normalize_title(cells[-1]) if cells else ""


def _looks_like_identifier(value: str) -> bool:
    text = value.strip()
    if not re.search(r"\d", text):
        return False
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9 _-]{2,60}", text, flags=re.IGNORECASE))


def _is_internal_identifier_block(value: str) -> bool:
    text = value.strip()
    if "rex-prod" in text.lower():
        return True
    if re.search(r"\b[A-Z]{2,10}-[A-Z]-\d{4}-\d{1,2}-\d{2,}\b", text, flags=re.IGNORECASE):
        return True
    return False


def _is_action_text(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith(("view submission", "contact journal", "manuscript files", "action"))


def _prefer_record(
    existing: ManuscriptRecord | None,
    candidate: ManuscriptRecord,
) -> ManuscriptRecord:
    if existing is None:
        return candidate
    if status_score(candidate.status) > status_score(existing.status):
        return candidate
    if not existing.manuscript_id and candidate.manuscript_id:
        return candidate
    if identity_title(candidate.title) == identity_title(existing.title):
        return existing
    return candidate
