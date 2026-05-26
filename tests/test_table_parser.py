from ieee_scholarone_monitor.models import JournalAccount
from ieee_scholarone_monitor.parsing.table_parser import parse_table_rows


def _journal() -> JournalAccount:
    return JournalAccount(
        key="ieee-tcyb",
        name="IEEE TCYB",
        platform="scholarone",
        url="https://mc.manuscriptcentral.com/cyb-ieee",
        username="alice",
        password="secret",
    )


def test_parse_table_rows_extracts_current_status():
    rows = [
        ["Help", "Logout"],
        [
            "TCYB-2026-001",
            "A careful paper about cybernetics",
            "Under Review\nSubmitted 01-May-2026",
            "View Submission",
        ],
    ]

    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    assert len(records) == 1
    assert records[0].manuscript_id == "TCYB-2026-001"
    assert records[0].title == "A careful paper about cybernetics"
    assert records[0].status == "Under Review"


def test_parse_table_rows_marks_terminal_status_archived():
    rows = [["TNNLS-2026-100", "Another careful paper", "Accepted"]]

    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    assert records[0].archived is True


def test_parse_table_rows_ignores_date_tokens_and_internal_ids():
    rows = [
        [
            "Apr-2026",
            "CYB-E-2026-04-1672 (REX-PROD-2-0641EBD9-09BF-4419-AE1E-AB2E25DFEE00-C67730BB-F4CF-4408-A62A-06A07DDBC8E1-99152)",
            "A careful paper about cybernetics",
            "Under Review",
        ]
    ]

    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    assert len(records) == 1
    assert records[0].manuscript_id == "CYB-E-2026-04-1672"
    assert records[0].title == "A careful paper about cybernetics"
    assert records[0].status == "Under Review"
