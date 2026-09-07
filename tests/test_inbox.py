"""Inbox tests use synthetic messages and mocked Google calls only."""
import base64
from email.message import EmailMessage
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response
from streamlit.testing.v1 import AppTest

from email_assistant.email import gmail
from email_assistant.ui import pages


def resource(message, id="one", timestamp="1700000000000"):
    return dict(id=id, internalDate=timestamp, snippet="Hello &amp; welcome",
                raw=base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("="))


def plain():
    message = EmailMessage()
    message["From"] = "José <jose@example.com>"
    message["Subject"] = "Hello 世界"
    message.set_content("Hello café\nSecond line", charset="utf-8")
    return message


def test_plain_headers_date_and_unpadded_base64():
    email = gmail.parse_inbox_message(resource(plain()))
    assert email.sender == "José <jose@example.com>"
    assert email.subject == "Hello 世界"
    assert email.body == "Hello café\nSecond line"
    assert email.snippet == "Hello & welcome"
    assert email.received_at.timestamp() == 1700000000


def test_nested_alternative_and_attachments():
    message = plain()
    message.add_alternative("<p>Duplicate HTML</p>", subtype="html")
    message.add_attachment("Private attachment text", filename="notes.txt")
    assert gmail.parse_inbox_message(resource(message)).body == "Hello café\nSecond line"


def test_html_related_ignores_remote_images_and_scripts():
    message = EmailMessage()
    message.set_content('<html><head><style>hidden</style></head><body><p>Hello &amp; welcome</p><div>Next<br>line</div><script>secret script</script><img src="https://example.com/pixel"></body></html>', subtype="html")
    message.add_related(b"image", maintype="image", subtype="png", cid="<image>")
    email = gmail.parse_inbox_message(resource(message))
    assert "Hello & welcome" in email.body
    assert "Next\nline" in email.body
    assert all(value not in email.body for value in ("hidden", "script", "https://", "<p>"))
    assert email.subject == "(No subject)"
    assert email.sender == "Unknown sender"


@pytest.mark.parametrize("charset", ["iso-8859-1", "unknown-charset"])
def test_charsets_and_quoted_printable(charset):
    raw = f"Content-Type: text/plain; charset={charset}\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\ncaf=E9".encode()
    data = resource(plain())
    data["raw"] = base64.urlsafe_b64encode(raw).decode()
    assert gmail.parse_inbox_message(data).body == ("café" if charset == "iso-8859-1" else "caf�")


def test_attachment_only_body():
    message = EmailMessage()
    message.add_attachment(b"data", maintype="application", subtype="pdf", filename="file.pdf")
    assert "No readable text body" in gmail.parse_inbox_message(resource(message)).body


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(gmail, "get_credentials", MagicMock())
    monkeypatch.setattr(gmail, "AuthorizedHttp", MagicMock())
    service = MagicMock()
    service.__enter__.return_value = service
    monkeypatch.setattr(gmail, "build", MagicMock(return_value=service))
    messages = service.users().messages()
    messages.list().execute.return_value = {"messages": [{"id": "one"}, {"id": "two"}]}
    messages.get().execute.side_effect = [resource(plain()), resource(plain(), "two", "1800000000000")]
    return messages


def test_latest_ten_inbox_only_sorted_and_read_only(api):
    assert [email.id for email in gmail.fetch_inbox()] == ["two", "one"]
    gmail.get_credentials.assert_called_once_with(gmail.INBOX_SCOPES)
    api.list.assert_called_with(userId="me", labelIds=["INBOX"], maxResults=10)
    assert api.get.call_args.kwargs == dict(userId="me", id="two", format="raw")
    api.modify.assert_not_called()
    api.send.assert_not_called()


def test_empty_inbox(api):
    api.list().execute.return_value = {}
    api.get.reset_mock()
    assert gmail.fetch_inbox() == []
    api.get.assert_not_called()


@pytest.mark.parametrize("error,match", [
    (HttpError(Response({"status": 401}), b"secret token"), "expired or was revoked"),
    (HttpError(Response({"status": 403}), b"secret token"), "denied inbox access"),
    (HttpError(Response({"status": 429}), b"secret token"), "too many requests"),
    (HttpError(Response({"status": 500}), b"secret token"), "could not load"),
    (TimeoutError("secret token"), "network"),
    (RefreshError("secret token"), "authorization"),
])
def test_errors_are_safe(api, error, match, caplog):
    api.list().execute.side_effect = error
    with pytest.raises(gmail.InboxError, match=match) as caught:
        gmail.fetch_inbox()
    assert "secret token" not in str(caught.value) + caplog.text


def test_disappeared_message_skipped(api):
    api.get().execute.side_effect = [HttpError(Response({"status": 404}), b"private"), resource(plain())]
    assert len(gmail.fetch_inbox()) == 1


def test_malformed_response_safe(api):
    api.get().execute.side_effect = [{"raw": "!bad!"}]
    with pytest.raises(gmail.InboxError, match="unreadable response"):
        gmail.fetch_inbox()


def test_send_only_token_upgraded_then_reused_by_sending(tmp_path, monkeypatch):
    monkeypatch.setattr(gmail, "PROJECT_ROOT", tmp_path)
    (tmp_path / "token.json").touch()
    (tmp_path / "credentials.json").touch()
    old = MagicMock(valid=True, scopes=gmail.SCOPES)
    new = MagicMock(valid=True, scopes=gmail.INBOX_SCOPES)
    loader = MagicMock(return_value=old)
    monkeypatch.setattr(gmail.Credentials, "from_authorized_user_file", loader)
    flow = MagicMock()
    flow.run_local_server.return_value = new
    factory = MagicMock(return_value=flow)
    monkeypatch.setattr(gmail.InstalledAppFlow, "from_client_secrets_file", factory)
    monkeypatch.setattr(gmail, "_save_token", MagicMock())
    assert gmail.get_credentials(gmail.INBOX_SCOPES) is new
    assert factory.call_args.args[1] == gmail.INBOX_SCOPES
    loader.return_value = new
    assert gmail.get_credentials() is new
    factory.assert_called_once()


def test_inbox_ui_refresh_cache_body_and_error(monkeypatch):
    fetch = MagicMock(return_value=[gmail.parse_inbox_message(resource(plain()))])
    monkeypatch.setattr(pages, "fetch_inbox", fetch)
    app = AppTest.from_string("from email_assistant.ui.pages import render_inbox\nrender_inbox()")
    app.run()
    assert not app.exception

    assert any("Hello café\nSecond line" == text.value for text in app.text)
    assert len(app.expander) == 1
    app.run()
    fetch.assert_called_once()
    fetch.return_value = []
    app.button[0].click().run()
    assert "empty" in app.info[0].value
    fetch.side_effect = gmail.InboxError("Could not connect to Gmail.")
    app.button[0].click().run()
    assert app.error[0].value == "Could not connect to Gmail."
    assert not app.expander
    assert not app.exception


def test_full_app_refresh_calls_gmail_and_renders_ten(api, caplog):
    api.list().execute.return_value = {"messages": [{"id": str(i)} for i in range(10)]}
    api.get().execute.side_effect = [
        resource(plain(), str(i), str(1700000000000 + i * 1000))
        for _ in range(2) for i in range(10)
    ]
    api.list.reset_mock()
    api.get.reset_mock()
    app = AppTest.from_file(str(gmail.PROJECT_ROOT / "app.py"))
    app.run()
    app.button(key="nav_Inbox").click().run()
    assert not app.exception
    assert len(app.expander) == 10
    refresh = next(button for button in app.button if button.label == "Refresh Inbox")
    refresh.click().run()
    assert not app.exception
    assert len(app.expander) == 10
    assert api.list.call_count == 2
    api.list.assert_called_with(userId="me", labelIds=["INBOX"], maxResults=10)
    assert api.get.call_count == 20
    assert [email.id for email in app.session_state.inbox_emails] == list(reversed([str(i) for i in range(10)]))
    api.send.assert_not_called()
    for stage in ("Gmail list returned", "parsed", "returning", "Streamlit received", "render completed"):
        assert f"{stage} count=10" in caplog.text
    assert "jose@example.com" not in caplog.text
    assert "Hello café" not in caplog.text
    assert any("received and rendered 10 messages" in caption.value for caption in app.caption)
    app.run()
    assert len(app.expander) == 10
    assert api.list.call_count == 2


def test_unexpected_inbox_error_is_visible_safe_and_retryable(monkeypatch, caplog):
    fetch = MagicMock(side_effect=RuntimeError("secret token and private email"))
    monkeypatch.setattr(pages, "fetch_inbox", fetch)
    app = AppTest.from_string("from email_assistant.ui.pages import render_inbox\nrender_inbox()")
    app.run()
    assert not app.exception
    assert "unexpected error" in app.error[0].value
    assert "RuntimeError" in caplog.text
    assert "secret token" not in app.error[0].value + caplog.text
    assert not app.info
    fetch.side_effect = None
    fetch.return_value = [gmail.parse_inbox_message(resource(plain()))]
    app.button[0].click().run()
    assert not app.error
    assert len(app.expander) == 1
