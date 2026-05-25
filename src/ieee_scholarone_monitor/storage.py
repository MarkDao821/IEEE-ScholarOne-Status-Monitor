from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .models import StatusSnapshot


def load_snapshot(path: Path) -> StatusSnapshot | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if "manuscripts" in data:
        return StatusSnapshot.from_dict(data)

    journals = data.get("journals", {})
    records = []
    checked_at = str(data.get("checked_at", ""))
    if isinstance(journals, dict):
        for journal_data in journals.values():
            if not isinstance(journal_data, dict):
                continue
            checked_at = str(journal_data.get("checked_at", checked_at))
            records.extend(journal_data.get("manuscripts", []))
    return StatusSnapshot.from_dict({"checked_at": checked_at, "manuscripts": records})


def save_snapshot(path: Path, snapshot: StatusSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, dict] = {}
    for record in snapshot.manuscripts:
        entry = grouped.setdefault(
            record.journal_key,
            {
                "journal_name": record.journal_name,
                "checked_at": snapshot.checked_at,
                "manuscripts": [],
            },
        )
        entry["manuscripts"].append(record.to_dict())

    payload = {"checked_at": snapshot.checked_at, "journals": grouped}
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=path.parent,
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(json.dumps(payload, ensure_ascii=False, indent=2))
            tmp_file.write("\n")
        tmp_path.replace(path)
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise
