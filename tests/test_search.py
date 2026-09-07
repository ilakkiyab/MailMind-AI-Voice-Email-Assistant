"""Search integration tests; no real Gmail access, recordings or credentials."""

import io
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response
from streamlit.testing.v1 import AppTest

from email_assistant.email import gmail
from email_assistant.ui import search
from email_assistant import voice
from tests.test_inbox import api, plain, resource


@pytest.mark.parametrize("query,expected", [
    ("Find emails from Google", 'from:"Google"'),
    ("Find emails from Unstop", 'from:"Unstop"'),
    ("Show emails about placement", "placement"),
    ("Show emails containing interview", "interview"),
    ("Find emails about assessment", "assessment"),
    ("Show me emails from Jane Doe.", 'from:"Jane Doe"'),
    ("  placement  ", "placement"),
    ('from:google.com subject:interview newer_than:7d', 'from:google.com subject:interview newer_than:7d'),
])
def test_query_conversion(query, expected):
    assert gmail.build_search_query(query) == expected


@pytest.mark.parametrize("query", ["", "  ", None, "Find emails about ..."])
def test_empty_query_does_not_authenticate(monkeypatch, query):
    auth = MagicMock()
    monkeypatch.setattr(gmail, "get_credentials", auth)
    with pytest.raises(gmail.EmailSearchError):
        gmail.search_emails(query)
    auth.assert_not_called()


def test_search_inbox_only_uses_existing_auth_and_parser(api):
    assert [email.id for email in gmail.search_emails("Find emails from Google")] == ["two", "one"]
    gmail.get_credentials.assert_called_once_with(gmail.INBOX_SCOPES)
    api.list.assert_called_with(userId="me", labelIds=["INBOX"], q='from:"Google"', maxResults=20)
    api.get.assert_called_with(userId="me", id="two", format="raw")
    api.modify.assert_not_called()
    api.send.assert_not_called()


def test_empty_results(api):
    api.list().execute.return_value = {}
    api.get.reset_mock()
    assert gmail.search_emails("no-match") == []
    api.get.assert_not_called()


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_safe_api_errors(api, status):
    api.list().execute.side_effect = HttpError(Response({"status": status}), b"secret token")
    with pytest.raises(gmail.EmailSearchError) as caught:
        gmail.search_emails("interview")
    assert "secret token" not in str(caught.value)


@pytest.mark.parametrize("error", [TimeoutError("secret"), RefreshError("secret"), ValueError("secret")])
def test_network_auth_and_bad_response(api, error):
    api.list().execute.side_effect = error
    with pytest.raises(gmail.EmailSearchError) as caught:
        gmail.search_emails("interview")
    assert "secret" not in str(caught.value)


def test_auth_setup_failure(api):
    gmail.get_credentials.side_effect = gmail.EmailDeliveryError("Gmail authentication failed.")
    with pytest.raises(gmail.EmailSearchError, match="authentication"):
        gmail.search_emails("interview")


def test_deleted_match_is_skipped(api):
    api.get().execute.side_effect = [HttpError(Response({"status": 404}), b"gone"), resource(plain(), "two")]
    assert [email.id for email in gmail.search_emails("interview")] == ["two"]


def app():
    return AppTest.from_string("from email_assistant.ui.search import render_search\nrender_search()").run()


def test_typed_search_results_persist_clear_and_isolation(monkeypatch):
    fetch = MagicMock(return_value=[gmail.parse_inbox_message(resource(plain()))])
    monkeypatch.setattr(search, "search_emails", fetch)
    page = app()
    fetch.assert_not_called()
    page.session_state.voice_transcription = "compose instruction"
    page.session_state.inbox_emails = ["existing inbox"]
    page.text_area(key="search_query").set_value("Show emails containing interview")
    page.button(key="search_submit").click().run()
    assert not page.exception
    fetch.assert_called_once_with("Show emails containing interview")
    assert len(page.expander) == 1
    assert any("José" in item.value for item in page.text)
    assert any("Received:" in item.value for item in page.caption)
    page.run()
    fetch.assert_called_once()
    page.button(key="search_clear").click().run()
    assert not page.exception
    assert page.text_area(key="search_query").value == ""
    assert not page.expander
    assert page.session_state.voice_transcription == "compose instruction"
    assert page.session_state.inbox_emails == ["existing inbox"]
    assert page.session_state.search_recording_version == 1


def test_empty_results_and_safe_retry(monkeypatch):
    fetch = MagicMock(return_value=[])
    monkeypatch.setattr(search, "search_emails", fetch)
    page = app()
    page.text_area(key="search_query").set_value("xyz")
    page.button(key="search_submit").click().run()
    assert "No emails matched" in page.info[0].value
    for error in (gmail.EmailSearchError("Check your network."), RuntimeError("secret token")):
        fetch.side_effect = error
        page.button(key="search_submit").click().run()
        assert not page.exception
        assert page.error and not page.info
        assert "secret" not in page.error[0].value
    fetch.side_effect = None
    page.button(key="search_submit").click().run()
    assert not page.error
    assert page.info


def test_voice_uses_real_transcription_entrypoint_and_allows_edit(monkeypatch):
    data = io.BytesIO()
    with wave.open(data, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)
    data.name = "search.wav"
    data.type = "audio/wav"
    monkeypatch.setattr(search.st, "audio_input", lambda *args, **kwargs: data)
    model = MagicMock()
    model.transcribe.return_value = ([SimpleNamespace(text="Find emails from Google")], None)
    monkeypatch.setattr(voice, "_get_model", lambda: model)
    fetch = MagicMock(return_value=[])
    monkeypatch.setattr(search, "search_emails", fetch)
    page = app()
    page.button(key="search_transcribe").click().run()
    assert not page.exception
    assert page.text_area(key="search_query").value == "Find emails from Google"
    model.transcribe.assert_called_once()
    assert model.transcribe.call_args.kwargs == dict(language="en", beam_size=1, vad_filter=True)
    fetch.assert_not_called()
    page.text_area(key="search_query").set_value("Find emails from Unstop")
    page.button(key="search_submit").click().run()
    fetch.assert_called_once_with("Find emails from Unstop")


def test_missing_recording_and_transcription_failure_preserve_text(monkeypatch):
    monkeypatch.setattr(search.st, "audio_input", lambda *args, **kwargs: None)
    page = app()
    page.text_area(key="search_query").set_value("placement")
    page.button(key="search_transcribe").click().run()
    assert page.warning and not page.exception
    monkeypatch.setattr(search.st, "audio_input", lambda *args, **kwargs: io.BytesIO(b"bad"))
    page.button(key="search_transcribe").click().run()
    assert page.warning and not page.exception
    assert page.text_area(key="search_query").value == "placement"


def test_navigation():
    from email_assistant.ui.app import NAV_ITEMS
    from email_assistant.ui.pages import FEATURES, PAGE_RENDERERS
    assert "Voice Email Search" in NAV_ITEMS
    assert PAGE_RENDERERS["Voice Email Search"] is search.render_search
    assert any(feature[3] == "Voice Email Search" for feature in FEATURES)
