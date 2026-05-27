import httpx

from ieee_scholarone_monitor.notifier import (
    EmailNotifier,
    ServerChanTurboNotifier,
    format_changes_message,
    format_report_message,
)
from ieee_scholarone_monitor.models import ManuscriptRecord, StatusChange


CURRENT_MANUSCRIPT_ID = "DEMO-E-2026-04-0001"
ARCHIVED_MANUSCRIPT_ID = "DEMO-E-2025-12-0002"
MANUSCRIPT_TITLE = "Example Manuscript Title for Notification Tests"


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


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logins = []
        self.messages = []
        self.quit_called = False
        FakeSMTP.instances.append(self)

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.logins.append((username, password))

    def send_message(self, message, from_addr, to_addrs):
        self.messages.append((message, from_addr, to_addrs))

    def quit(self):
        self.quit_called = True


def test_email_notifier_sends_plain_text_message_to_multiple_recipients():
    FakeSMTP.instances = []
    notifier = EmailNotifier(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        username="sender@example.com",
        password="fake-email-credential",
        from_address="sender@example.com",
        to_addresses=("one@example.com", "two@example.com"),
        smtp_factory=FakeSMTP,
    )

    result = notifier.send("Status Update", "Body text")

    assert result.ok is True
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.gmail.com"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.logins == [("sender@example.com", "fake-email-credential")]
    message, from_addr, to_addrs = smtp.messages[0]
    assert message["Subject"] == "Status Update"
    assert message["From"] == "sender@example.com"
    assert message["To"] == "one@example.com, two@example.com"
    assert message.get_body(("plain",)).get_content().strip() == "Body text"
    assert from_addr == "sender@example.com"
    assert to_addrs == ["one@example.com", "two@example.com"]
    assert smtp.quit_called is True


def test_email_notifier_adds_html_body_with_highlighted_escaped_status():
    FakeSMTP.instances = []
    body = format_report_message(
        [
            ManuscriptRecord(
                journal_key="ieee-tcyb",
                journal_name="IEEE TCYB",
                manuscript_id="TCYB-2026-001",
                title="A <Paper> & Notes",
                status="Under <Review> & Ready",
                url="https://example.test",
                checked_at="2026-05-25T00:00:00+00:00",
            )
        ]
    )
    notifier = EmailNotifier(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        username="sender@example.com",
        password="fake-email-credential",
        from_address="sender@example.com",
        to_addresses=("one@example.com", "two@example.com"),
        smtp_factory=FakeSMTP,
    )

    result = notifier.send("Status Update", body)

    assert result.ok is True
    message = FakeSMTP.instances[0].messages[0][0]
    assert message.is_multipart() is True
    assert message.get_body(("plain",)).get_content().strip() == body
    html = message.get_body(("html",)).get_content()
    assert "background-color:" in html
    assert "Under &lt;Review&gt; &amp; Ready" in html
    assert "A &lt;Paper&gt; &amp; Notes" in html
    assert "Under <Review> & Ready" not in html


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
    assert "Title: A Paper" in body
    assert "```\nUnder Review\n```" in body
    assert "Current Status:" not in body
    assert "**Title:**" not in body
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
    assert "Title: A Paper" in lines
    assert "```" in lines
    assert "Under Review" in lines
    assert "Current Status: Under Review" not in lines
    assert "Created: 27-Apr-2026" in lines
    assert "Submitted: 28-Apr-2026" in lines
    assert "Checked At: 2026-05-25 08:00:00" in lines
    assert "Submission System: https://example.test" in lines


def test_report_message_includes_archived_table_records():
    body = format_report_message(
        [
            ManuscriptRecord(
                journal_key="ieee-tcyb",
                journal_name="IEEE TCYB",
                manuscript_id=CURRENT_MANUSCRIPT_ID,
                title=MANUSCRIPT_TITLE,
                status="Under Review",
                url="https://example.test",
                checked_at="2026-05-26T08:00:00+00:00",
                created_at="27-Apr-2026",
                submitted_at="27-Apr-2026",
            ),
            ManuscriptRecord(
                journal_key="ieee-tcyb",
                journal_name="IEEE TCYB",
                manuscript_id=ARCHIVED_MANUSCRIPT_ID,
                title=MANUSCRIPT_TITLE,
                status="Reject & Resubmit (09-Mar-2026)",
                url="https://example.test",
                checked_at="2026-05-26T08:00:00+00:00",
                created_at="20-Dec-2025",
                submitted_at="20-Dec-2025",
                archived=True,
            ),
        ]
    )

    assert CURRENT_MANUSCRIPT_ID in body
    assert ARCHIVED_MANUSCRIPT_ID in body
    assert "```\nReject & Resubmit (09-Mar-2026)\n```" in body
    assert "Current Status:" not in body


def test_changes_message_formats_title_and_status_like_root_push():
    body = format_changes_message(
        [
            StatusChange(
                kind="status_changed",
                journal_key="ieee-tcyb",
                journal_name="IEEE TCYB",
                manuscript_id="TCYB-2026-001",
                title="A Paper",
                previous_status="Awaiting Reviewer Scores",
                current_status="Under Review",
                checked_at="2026-05-25T00:00:00+00:00",
                url="https://example.test",
                created_at="27-Apr-2026",
                submitted_at="28-Apr-2026",
            )
        ]
    )

    assert "Title: A Paper" in body
    assert "Previous Status: Awaiting Reviewer Scores" in body
    assert "```\nUnder Review\n```" in body
    assert "Current Status:" not in body
    assert "**Title:**" not in body
    assert "**Current Status:**" not in body
