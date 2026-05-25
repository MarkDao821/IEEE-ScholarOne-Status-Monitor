from ieee_scholarone_monitor.models import ManuscriptRecord, StatusSnapshot
from ieee_scholarone_monitor.storage import load_snapshot, save_snapshot


def test_save_and_load_grouped_snapshot(tmp_path):
    path = tmp_path / "status.json"
    snapshot = StatusSnapshot(
        checked_at="2026-05-25T00:00:00+00:00",
        manuscripts=(
            ManuscriptRecord(
                journal_key="ieee-tcyb",
                journal_name="IEEE TCYB",
                manuscript_id="TCYB-2026-001",
                title="A Paper",
                status="Under Review",
                url="https://example.test",
                checked_at="2026-05-25T00:00:00+00:00",
            ),
        ),
    )

    save_snapshot(path, snapshot)
    loaded = load_snapshot(path)

    assert loaded == snapshot
