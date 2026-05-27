"""测试状态快照的保存和读取。

测试什么：
- 把当前稿件状态保存成 JSON 文件。
- 再从 JSON 文件读回来，并确认内容没有变化。

需要填写什么：
- 不需要填写真实文件路径，pytest 会提供临时目录 tmp_path。
- 不需要填写真实稿件信息，测试里使用合成稿件记录。
"""

from ieee_scholarone_monitor.models import ManuscriptRecord, StatusSnapshot
from ieee_scholarone_monitor.storage import load_snapshot, save_snapshot


def test_save_and_load_grouped_snapshot(tmp_path):
    # tmp_path is a pytest-provided temporary folder. It lets the test write a
    # file without touching the real project data files.
    path = tmp_path / "status.json"

    # This is the in-memory snapshot we expect to save and load back unchanged.
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

    # Save to disk, then read it back.
    save_snapshot(path, snapshot)
    loaded = load_snapshot(path)

    # Dataclasses compare by value, so this checks every field in the snapshot.
    assert loaded == snapshot
