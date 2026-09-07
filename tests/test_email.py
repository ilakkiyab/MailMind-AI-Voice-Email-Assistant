"""No real OAuth, credentials, or Gmail calls in these tests."""

import base64
from email import policy
from email.parser import BytesParser
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response
from oauthlib.oauth2 import AccessDeniedError
from requests.exceptions import ConnectionError

from email_assistant.email import EmailDeliveryError
from email_assistant.email import gmail


@pytest.mark.parametrize("values", [
    ("", "Subject", "Body"), ("a@example.com", " ", "Body"),
    ("a@example.com", "Subject", ""), ("invalid", "Subject", "Body"),
    ("a@example.com,b@example.com", "Subject", "Body"),
    ("a@example.com\nBcc: b@example.com", "Subject", "Body"),
    ("a@example.com", "Subject\r\nBcc: b@example.com", "Body"),
])
def test_invalid_email_does_not_authenticate(values, monkeypatch):
    auth = MagicMock()
    monkeypatch.setattr(gmail, "get_credentials", auth)
    with pytest.raises(EmailDeliveryError):
        gmail.send_email(*values)
    auth.assert_not_called()


@pytest.fixture
def oauth(tmp_path, monkeypatch):
    monkeypatch.setattr(gmail, "PROJECT_ROOT", tmp_path)
    return tmp_path


def test_missing_credentials(oauth):
    with pytest.raises(EmailDeliveryError, match="credentials are missing"):
        gmail.get_credentials()


def test_unwritable_token_is_reported_before_sending(oauth, monkeypatch):
    (oauth / "credentials.json").touch()
    monkeypatch.setattr(gmail.InstalledAppFlow, "from_client_secrets_file", MagicMock())
    monkeypatch.setattr(gmail, "_save_token", MagicMock(side_effect=PermissionError()))
    with pytest.raises(EmailDeliveryError, match="file permissions"):
        gmail.get_credentials()


def test_valid_token_reused_without_client_file(oauth, monkeypatch):
    (oauth / "token.json").touch()
    creds = MagicMock(valid=True, scopes=gmail.SCOPES)
    monkeypatch.setattr(gmail.Credentials, "from_authorized_user_file", lambda *a: creds)
    assert gmail.get_credentials() is creds
    creds.refresh.assert_not_called()


def test_expired_token_refreshed_and_saved(oauth, monkeypatch):
    (oauth / "token.json").touch()
    creds = MagicMock(valid=False, expired=True, refresh_token="test-only", scopes=gmail.SCOPES)
    creds.refresh.side_effect = lambda request: setattr(creds, "valid", True)
    creds.to_json.return_value = '{"test": true}'
    monkeypatch.setattr(gmail.Credentials, "from_authorized_user_file", lambda *a: creds)
    assert gmail.get_credentials() is creds
    creds.refresh.assert_called_once()
    assert (oauth / "token.json").read_text() == '{"test": true}'
    assert not list(oauth.glob(".oauth-*.tmp"))


@pytest.mark.parametrize("token_state", ["missing", "corrupt", "revoked", "wrong_scope"])
def test_oauth_flow_and_reauthorization(oauth, monkeypatch, token_state):
    (oauth / "credentials.json").touch()
    old = MagicMock(valid=False, expired=True, refresh_token="test-only", scopes=gmail.SCOPES)
    old.refresh.side_effect = RefreshError("revoked")
    loader = MagicMock(return_value=old)
    if token_state != "missing":
        (oauth / "token.json").touch()
    if token_state == "corrupt":
        loader.side_effect = ValueError("corrupt")
    if token_state == "wrong_scope":
        old.scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
    monkeypatch.setattr(gmail.Credentials, "from_authorized_user_file", loader)
    flow = MagicMock()
    flow.run_local_server.return_value.to_json.return_value = '{"test": true}'
    factory = MagicMock(return_value=flow)
    monkeypatch.setattr(gmail.InstalledAppFlow, "from_client_secrets_file", factory)
    assert gmail.get_credentials() is flow.run_local_server.return_value
    assert factory.call_args.args[1] == gmail.SCOPES
    assert factory.call_args.args[0] == str(oauth / "credentials.json")
    assert flow.run_local_server.call_args.kwargs["timeout_seconds"] == 120


@pytest.mark.parametrize("error", [ValueError("secret"), TypeError("secret"), TimeoutError("secret"), AttributeError("secret")])
def test_authentication_errors_are_safe(oauth, monkeypatch, error):
    (oauth / "credentials.json").touch()
    monkeypatch.setattr(gmail.InstalledAppFlow, "from_client_secrets_file", MagicMock(side_effect=error))
    with pytest.raises(EmailDeliveryError) as caught:
        gmail.get_credentials()
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("error", [AccessDeniedError(), TimeoutError(), ConnectionError()])
def test_cancelled_or_failed_browser_flow(oauth, monkeypatch, error):
    (oauth / "credentials.json").touch()
    flow = MagicMock()
    flow.run_local_server.side_effect = error
    monkeypatch.setattr(gmail.InstalledAppFlow, "from_client_secrets_file", MagicMock(return_value=flow))
    with pytest.raises(EmailDeliveryError):
        gmail.get_credentials()
    assert not (oauth / "token.json").exists()


def test_incomplete_authorization_is_not_saved(oauth, monkeypatch):
    (oauth / "credentials.json").touch()
    flow = MagicMock()
    flow.run_local_server.return_value = None
    monkeypatch.setattr(gmail.InstalledAppFlow, "from_client_secrets_file", MagicMock(return_value=flow))
    with pytest.raises(EmailDeliveryError, match="not completed"):
        gmail.get_credentials()
    assert not (oauth / "token.json").exists()


def test_refresh_network_failure_is_friendly(oauth, monkeypatch):
    (oauth / "token.json").touch()
    creds = MagicMock(valid=False, expired=True, refresh_token=True, scopes=gmail.SCOPES)
    creds.refresh.side_effect = ConnectionError()
    monkeypatch.setattr(gmail.Credentials, "from_authorized_user_file", MagicMock(return_value=creds))
    with pytest.raises(EmailDeliveryError, match="network"):
        gmail.get_credentials()


def test_auth_failure_prevents_api_creation(monkeypatch):
    monkeypatch.setattr(gmail, "get_credentials", MagicMock(side_effect=EmailDeliveryError("Authorization failed")))
    builder = MagicMock()
    monkeypatch.setattr(gmail, "build", builder)
    with pytest.raises(EmailDeliveryError):
        gmail.send_email("person@example.com", "Subject", "Body")
    builder.assert_not_called()


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(gmail, "get_credentials", MagicMock())
    monkeypatch.setattr(gmail, "AuthorizedHttp", MagicMock())
    service = MagicMock()
    service.__enter__.return_value = service
    monkeypatch.setattr(gmail, "build", MagicMock(return_value=service))
    service.users().messages().send().execute.return_value = {"id": "message-123"}
    return service


def test_send_unicode_mime_once(api):
    assert gmail.send_email("person@example.com", "Hello café", "Hi,\n世界") == "message-123"
    sender = api.users().messages().send
    assert sender.call_args.kwargs["userId"] == "me"
    raw = sender.call_args.kwargs["body"]["raw"]
    message = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(raw))
    assert message["To"] == "person@example.com"
    assert message["Subject"] == "Hello café"
    assert message.get_content().strip() == "Hi,\n世界"
    sender().execute.assert_called_once_with(num_retries=0)


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_api_errors(api, status):
    api.users().messages().send().execute.side_effect = HttpError(Response({"status": status}), b"private details")
    with pytest.raises(EmailDeliveryError) as caught:
        gmail.send_email("person@example.com", "Subject", "Body")
    assert "private details" not in str(caught.value)


def test_network_error_warns_of_uncertain_delivery(api):
    api.users().messages().send().execute.side_effect = TimeoutError()
    with pytest.raises(EmailDeliveryError, match="Check Gmail Sent"):
        gmail.send_email("person@example.com", "Subject", "Body")


def test_missing_send_receipt(api):
    api.users().messages().send().execute.return_value = {}
    with pytest.raises(EmailDeliveryError, match="Check Gmail Sent"):
        gmail.send_email("person@example.com", "Subject", "Body")
