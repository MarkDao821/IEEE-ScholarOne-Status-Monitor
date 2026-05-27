"""测试两次状态快照之间的差异判断。

测试什么：
- 第一次运行时是否生成 baseline 变化。
- 稿件状态改变时是否识别为 status_changed。
- 稿件新增或移除时是否识别为 added 或 removed。

需要填写什么：
- 不需要填写真实稿件信息。
- 如果要新增场景，只需要在 _record() 里传入合成状态或合成稿件 ID。
"""

from ieee_scholarone_monitor.diff import diff_snapshots
from ieee_scholarone_monitor.models import ManuscriptRecord, StatusSnapshot


def _record(status: str, manuscript_id: str = "TCYB-2026-001") -> ManuscriptRecord:
    return ManuscriptRecord(
        journal_key="ieee-tcyb",
        journal_name="IEEE TCYB",
        manuscript_id=manuscript_id,
        title="A Paper",
        status=status,
        url="https://example.test",
        checked_at="2026-05-25T00:00:00+00:00",
    )


def test_diff_returns_baseline_for_first_snapshot():
    current = StatusSnapshot("now", (_record("Under Review"),))

    changes = diff_snapshots(None, current)

    assert [change.kind for change in changes] == ["baseline"]


def test_diff_detects_status_change():
    previous = StatusSnapshot("old", (_record("Submitted"),))
    current = StatusSnapshot("new", (_record("Under Review"),))

    changes = diff_snapshots(previous, current)

    assert len(changes) == 1
    assert changes[0].kind == "status_changed"
    assert changes[0].previous_status == "Submitted"
    assert changes[0].current_status == "Under Review"


def test_diff_detects_added_and_removed_records():
    previous = StatusSnapshot("old", (_record("Submitted", "A-1"),))
    current = StatusSnapshot("new", (_record("Submitted", "B-2"),))

    changes = diff_snapshots(previous, current)

    assert {change.kind for change in changes} == {"added", "removed"}
