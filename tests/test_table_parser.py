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
