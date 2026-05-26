import httpx

from ieee_scholarone_monitor.notifier import (
    ServerChanTurboNotifier,
    format_report_message,
)
from ieee_scholarone_monitor.models import ManuscriptRecord


class FakeClient:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.response

    def close(self):
        pass


def test_serverchan_send_success():
    client = FakeClient(httpx.Response(200, json={"code": 0}))
    notifier = ServerChanTurboNotifier("send-key", client=client)

    result = notifier.send("Title", "Body")

    assert result.ok is True
    assert client.requests[0][1]["data"] == {"title": "Title", "desp": "Body"}


def test_report_message_contains_current_status():
    body = format_report_message(
        [
            ManuscriptRecord(
                journal_key="ieee-tcyb",
                journal_name="IEEE TCYB",
                manuscript_id="TCYB-2026-001",
                title="A Paper",
                status="Under Review",
                url="https://example.test",
                checked_at="2026-05-25T00:00:00+00:00",
                created_at="27-Apr-2026",
                submitted_at="28-Apr-2026",
            )
        ]
    )

    assert "IEEE TCYB" in body
    assert "TCYB-2026-001" in body
    assert "**Title:**\n\n```text\nA Paper\n```" in body
    assert "**Current Status:**\n\n```text\nUnder Review\n```" in body
    assert "Created: 27-Apr-2026" in body
    assert "Submitted: 28-Apr-2026" in body
    assert "Checked At: 2026-05-25 08:00:00" in body
    assert "<span" not in body


def test_report_message_renders_each_property_on_its_own_line():
    body = format_report_message(
        [
            ManuscriptRecord(
                journal_key="ieee-tcyb",
                journal_name="IEEE TCYB",
                manuscript_id="TCYB-2026-001",
                title="A Paper",
                status="Under Review",
                url="https://example.test",
                checked_at="2026-05-25T00:00:00+00:00",
                created_at="27-Apr-2026",
                submitted_at="28-Apr-2026",
            )
        ]
    )

    lines = body.splitlines()

    assert "Journal: IEEE TCYB" in lines
    assert "Manuscript ID: TCYB-2026-001" in lines
    assert "**Title:**" in lines
    assert "A Paper" in lines
    assert "**Current Status:**" in lines
    assert "Under Review" in lines
    assert "Created: 27-Apr-2026" in lines
    assert "Submitted: 28-Apr-2026" in lines
    assert "Checked At: 2026-05-25 08:00:00" in lines
    assert "Submission System: https://example.test" in lines
