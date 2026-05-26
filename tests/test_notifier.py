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
            )
        ]
    )

    assert "IEEE TCYB" in body
    assert "TCYB-2026-001" in body
    assert 'Title: <span style="' in body
    assert ">A Paper</span>" in body
    assert 'Current Status: <span style="' in body
    assert ">Under Review</span>" in body


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
            )
        ]
    )

    lines = body.splitlines()

    assert "Journal: IEEE TCYB" in lines
    assert "Manuscript ID: TCYB-2026-001" in lines
    assert any(line.startswith("Title: <span style=") and "A Paper</span>" in line for line in lines)
    assert any(line.startswith("Current Status: <span style=") and "Under Review</span>" in line for line in lines)
    assert "Checked At: 2026-05-25T00:00:00+00:00" in lines
    assert "Submission System: https://example.test" in lines
