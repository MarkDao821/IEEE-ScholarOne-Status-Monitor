"""测试 ScholarOne 表格解析。

测试什么：
- 把类似 ScholarOne 页面表格的数据解析成稿件记录。
- 识别稿件 ID、标题、状态、创建日期、提交日期和 archived 标记。

需要填写什么：
- 不需要填写真实账号、真实稿件 ID 或真实论文标题。
- 新增测试数据时只写合成数据，例如 DEMO-E-2026-04-0001、Example Author。
"""

from ieee_scholarone_monitor.models import JournalAccount
from ieee_scholarone_monitor.parsing.table_parser import parse_table_rows


# These tests check the parser only. They do not open ScholarOne or use a real
# account. Every row below is a small fake table row that looks like ScholarOne.
#
# Test rows below are synthetic ScholarOne-like samples. Keep new fixtures generic:
# use fake manuscript IDs, fake titles, fake people, and fake internal IDs.
CURRENT_MANUSCRIPT_ID = "DEMO-E-2026-04-0001"
ARCHIVED_MANUSCRIPT_ID = "DEMO-E-2025-12-0002"
INTERNAL_ID_1 = "REX-PROD-DEMO-00000000-0000-0000-0000-000000000001"
INTERNAL_ID_2 = "REX-PROD-DEMO-00000000-0000-0000-0000-000000000002"
MANUSCRIPT_TITLE = "Example Manuscript Title for Parser Tests"


def _journal() -> JournalAccount:
    # This helper creates the minimum journal config required by the parser.
    # The username/password are fake and should not be replaced with real values.
    return JournalAccount(
        key="ieee-tcyb",
        name="IEEE TCYB",
        platform="scholarone",
        url="https://mc.manuscriptcentral.com/cyb-ieee",
        username="alice",
        password="secret",
    )


def test_parse_table_rows_extracts_current_status():
    # Arrange: build a simple table with one manuscript row.
    rows = [
        ["Help", "Logout"],
        [
            "TCYB-2026-001",
            "A careful paper about cybernetics",
            "Under Review\nSubmitted 01-May-2026",
            "View Submission",
        ],
    ]

    # Act: parse the fake table rows into ManuscriptRecord objects.
    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    # Assert: the parser should find the manuscript ID, title, and current status.
    assert len(records) == 1
    assert records[0].manuscript_id == "TCYB-2026-001"
    assert records[0].title == "A careful paper about cybernetics"
    assert records[0].status == "Under Review"


def test_parse_table_rows_marks_terminal_status_archived():
    # Terminal statuses such as "Accepted" should be kept but marked as archived.
    rows = [["TNNLS-2026-100", "Another careful paper", "Accepted"]]

    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    assert records[0].archived is True


def test_parse_table_rows_ignores_date_tokens_and_internal_ids():
    # ScholarOne pages may include dates and internal IDs near the visible
    # manuscript ID. The parser should ignore those extra tokens.
    rows = [
        [
            "Apr-2026",
            f"{CURRENT_MANUSCRIPT_ID} ({INTERNAL_ID_1})",
            "A careful paper about cybernetics",
            "Under Review",
        ]
    ]

    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    assert len(records) == 1
    assert records[0].manuscript_id == CURRENT_MANUSCRIPT_ID
    assert records[0].title == "A careful paper about cybernetics"
    assert records[0].status == "Under Review"


def test_parse_table_rows_uses_scholarone_headers_with_action_offset():
    # This is closer to a real ScholarOne table layout: a header row appears
    # first, and the data row includes action text such as "View Submission".
    rows = [
        ["STATUS", "ID", "TITLE", "CREATED", "SUBMITTED"],
        [
            "Contact Journal\n\nEIC: Example Editor\nADM: Example Admin\n\n\n\tUnder Review",
            "",
            "Under Review",
            f"{CURRENT_MANUSCRIPT_ID} ({INTERNAL_ID_1})",
            f"{MANUSCRIPT_TITLE}\n View Submission\nSubmitting Author: Example Author",
            "27-Apr-2026",
            "27-Apr-2026",
        ],
    ]

    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    assert len(records) == 1
    assert records[0].status == "Under Review"
    assert records[0].manuscript_id == CURRENT_MANUSCRIPT_ID
    assert records[0].title == MANUSCRIPT_TITLE
    assert records[0].created_at == "27-Apr-2026"
    assert records[0].submitted_at == "27-Apr-2026"


def test_parse_table_rows_keeps_all_manuscript_table_results():
    # Some ScholarOne tables include both current and archived manuscripts.
    # This test makes sure the parser returns both records instead of stopping
    # after the first one.
    rows = [
        ["STATUS", "ID", "TITLE", "CREATED", "SUBMITTED"],
        [
            "Contact Journal\n\nEIC: Example Editor\nADM: Example Admin\n\n\n\tUnder Review",
            "",
            "Under Review",
            f"{CURRENT_MANUSCRIPT_ID} ({INTERNAL_ID_1})",
            f"{MANUSCRIPT_TITLE}\n View Submission\nSubmitting Author: Example Author",
            "27-Apr-2026",
            "27-Apr-2026",
        ],
        ["", "Under Review"],
        [
            "Contact Journal\n\nEIC: Example Editor\nADM: Example Admin\n\n\n\tReject & Resubmit (09-Mar-2026)",
            "",
            "Reject & Resubmit (09-Mar-2026)",
            f"{ARCHIVED_MANUSCRIPT_ID} ({INTERNAL_ID_2})",
            f"{MANUSCRIPT_TITLE}\n View Submission\nSubmitting Author: Example Author",
            "20-Dec-2025",
            "20-Dec-2025",
        ],
        ["", "Reject & Resubmit (09-Mar-2026)"],
    ]

    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    assert [record.manuscript_id for record in records] == [
        CURRENT_MANUSCRIPT_ID,
        ARCHIVED_MANUSCRIPT_ID,
    ]
    assert [record.status for record in records] == [
        "Under Review",
        "Reject & Resubmit (09-Mar-2026)",
    ]
    assert records[1].archived is True
