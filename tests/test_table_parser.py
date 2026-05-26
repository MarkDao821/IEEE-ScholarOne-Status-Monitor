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


def test_parse_table_rows_uses_scholarone_headers_with_action_offset():
    rows = [
        ["STATUS", "ID", "TITLE", "CREATED", "SUBMITTED"],
        [
            "Contact Journal\n\nEIC: Shi, Peng\nADM: Lian, Zhi\n\n\n\tUnder Review",
            "",
            "Under Review",
            "CYB-E-2026-04-1672 (REX-PROD-2-0641EBD9-09BF-4419-AE1E-AB2E25DFEE00-C67730BB-F4CF-4408-A62A-06A07DDBC8E1-99152)",
            "Manifold Transfer Learning for Multitask Optimization\n View Submission\nSubmitting Author: Wang, Zijia",
            "27-Apr-2026",
            "27-Apr-2026",
        ],
    ]

    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    assert len(records) == 1
    assert records[0].status == "Under Review"
    assert records[0].manuscript_id == "CYB-E-2026-04-1672"
    assert records[0].title == "Manifold Transfer Learning for Multitask Optimization"
    assert records[0].created_at == "27-Apr-2026"
    assert records[0].submitted_at == "27-Apr-2026"


def test_parse_table_rows_keeps_all_manuscript_table_results():
    rows = [
        ["STATUS", "ID", "TITLE", "CREATED", "SUBMITTED"],
        [
            "Contact Journal\n\nEIC: Shi, Peng\nADM: Lian, Zhi\n\n\n\tUnder Review",
            "",
            "Under Review",
            "CYB-E-2026-04-1672 (REX-PROD-2-0641EBD9-09BF-4419-AE1E-AB2E25DFEE00-C67730BB-F4CF-4408-A62A-06A07DDBC8E1-99152)",
            "Manifold Transfer Learning for Multitask Optimization\n View Submission\nSubmitting Author: Wang, Zijia",
            "27-Apr-2026",
            "27-Apr-2026",
        ],
        ["", "Under Review"],
        [
            "Contact Journal\n\nEIC: Shi, Peng\nADM: Lian, Zhi\n\n\n\tReject & Resubmit (09-Mar-2026)",
            "",
            "Reject & Resubmit (09-Mar-2026)",
            "CYB-E-2025-12-4642 (REX-PROD-2-F8019E40-2A13-41CE-88A0-F39336F8A7E9-F5C052C8-1799-403D-94DD-AEEC7C7F660E-39355)",
            "Manifold Transfer Learning for Multitask Optimization\n View Submission\nSubmitting Author: Wang, Zijia",
            "20-Dec-2025",
            "20-Dec-2025",
        ],
        ["", "Reject & Resubmit (09-Mar-2026)"],
    ]

    records = parse_table_rows(_journal(), rows, "https://example.test", checked_at="now")

    assert [record.manuscript_id for record in records] == [
        "CYB-E-2026-04-1672",
        "CYB-E-2025-12-4642",
    ]
    assert [record.status for record in records] == [
        "Under Review",
        "Reject & Resubmit (09-Mar-2026)",
    ]
    assert records[1].archived is True
