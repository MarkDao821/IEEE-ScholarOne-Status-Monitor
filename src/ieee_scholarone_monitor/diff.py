from __future__ import annotations

from .models import ManuscriptRecord, StatusChange, StatusSnapshot


def _key(record: ManuscriptRecord) -> str:
    return f"{record.journal_key}:{record.identity}"


def _index(records: tuple[ManuscriptRecord, ...]) -> dict[str, ManuscriptRecord]:
    indexed: dict[str, ManuscriptRecord] = {}
    for record in records:
        key = _key(record)
        if key not in indexed:
            indexed[key] = record
    return indexed


def diff_snapshots(
    previous: StatusSnapshot | None,
    current: StatusSnapshot,
) -> list[StatusChange]:
    current_records = _index(current.manuscripts)
    changes: list[StatusChange] = []
    if previous is None:
        return [
            _change("baseline", record, "", record.status)
            for record in current_records.values()
            if not record.archived
        ]

    previous_records = _index(previous.manuscripts)
    for key, record in current_records.items():
        if record.archived:
            continue
        old = previous_records.get(key)
        if old is None:
            changes.append(_change("added", record, "", record.status))
        elif old.status != record.status:
            changes.append(_change("status_changed", record, old.status, record.status))

    for key, old in previous_records.items():
        if old.archived:
            continue
        if key not in current_records:
            changes.append(_change("removed", old, old.status, ""))
    return changes


def _change(
    kind: str,
    record: ManuscriptRecord,
    previous_status: str,
    current_status: str,
) -> StatusChange:
    return StatusChange(
        kind=kind,
        journal_key=record.journal_key,
        journal_name=record.journal_name,
        manuscript_id=record.manuscript_id,
        title=record.title,
        previous_status=previous_status,
        current_status=current_status,
        checked_at=record.checked_at,
        url=record.url,
        created_at=record.created_at,
        submitted_at=record.submitted_at,
    )
