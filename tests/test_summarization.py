"""Synthetic summarization tests; no live AI, OAuth or Gmail calls."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from email_assistant.ai import summarization as ai
from email_assistant.email.gmail import InboxEmail
from email_assistant.ui import pages


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setattr(ai, "_load_environment", lambda: None)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)


def client(output="- Meet Priya on 8 September.\n- Send the report by Friday."):
    result = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=output))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=MagicMock(return_value=result))))


def test_reuses_drafting_client_and_configuration(monkeypatch):
    fake = client()
    factory = MagicMock(return_value=fake)
    monkeypatch.setattr(ai, "_nvidia_client", factory)
    monkeypatch.setenv("NVIDIA_API_KEY", "synthetic-key")
    monkeypatch.setenv("NVIDIA_MODEL", "configured-model")
    body = "Meet Priya on 8 September. Send the report by Friday."
    summary = ai.summarize_email(body)
    factory.assert_called_once_with("synthetic-key")
    request = fake.chat.completions.create.call_args.kwargs
    assert request["model"] == "configured-model"
    assert request["messages"][1]["content"] == "EMAIL BODY:\n" + body
    assert request["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert "2–4" in request["messages"][0]["content"]
    assert "synthetic-key" not in str(request)
    assert "Priya" in summary.text and not summary.truncated


@pytest.mark.parametrize("body", ["", " \n ", None, ai.EMPTY_BODY, "<p> </p><script>hidden</script>"])
def test_empty_body_never_calls_provider(body):
    fake = client()
    with pytest.raises(ai.SummaryGenerationError, match="no readable body"):
        ai.summarize_email(body, client=fake)
    fake.chat.completions.create.assert_not_called()


def test_html_and_long_body_are_bounded():
    fake = client()
    summary = ai.summarize_email(
        '<head><style>hidden</style></head><p>Priya &amp; Lee</p><script>secret</script>'
        '<p>' + 'Meeting tomorrow. ' * 2000 + '</p><img src="https://example.com/pixel">',
        client=fake,
    )
    request = fake.chat.completions.create.call_args.kwargs
    content = request["messages"][1]["content"]
    assert "Priya & Lee" in content
    assert all(value not in content for value in ("hidden", "secret", "<p>", "https://"))
    assert len(content.split("\n", 1)[1]) == ai.MAX_BODY_CHARS
    assert summary.truncated
    assert request["model"] == ai.DEFAULT_MODEL


def test_missing_configuration():
    with pytest.raises(ai.SummaryGenerationError, match="not configured"):
        ai.summarize_email("Hello")


@pytest.mark.parametrize("status,match", [(401, "Authentication"), (403, "Authentication"),
    (429, "quota"), (500, "service error"), (404, "model"), (None, "service error")])
def test_provider_errors_are_safe(status, match, caplog):
    fake = client()
    error = RuntimeError("secret credentials and email authentication information")
    error.status_code = status
    fake.chat.completions.create.side_effect = error
    with pytest.raises(ai.SummaryGenerationError, match=match) as caught:
        ai.summarize_email("Hello", client=fake)
    assert "secret" not in str(caught.value) + caplog.text
    assert caught.value.__suppress_context__


@pytest.mark.parametrize("error", [TimeoutError("secret"), ConnectionError("secret")])
def test_network_errors(error):
    fake = client()
    fake.chat.completions.create.side_effect = error
    with pytest.raises(ai.SummaryGenerationError, match="network"):
        ai.summarize_email("Hello", client=fake)


@pytest.mark.parametrize("output", [None, "", "  ", 123])
def test_empty_or_invalid_response(output):
    with pytest.raises(ai.SummaryGenerationError, match="no usable summary"):
        ai.summarize_email("Hello", client=client(output))


def test_missing_choices():
    fake = client()
    fake.chat.completions.create.return_value = SimpleNamespace(choices=[])
    with pytest.raises(ai.SummaryGenerationError, match="no usable summary"):
        ai.summarize_email("Hello", client=fake)


def test_inbox_summary_is_specific_persistent_safe_and_retryable(monkeypatch, caplog):
    emails = [InboxEmail(str(i), "Sender", "Subject", datetime.now(timezone.utc), "Preview", f"Body {i}") for i in range(2)]
    fetch = MagicMock(return_value=emails)
    summarize = MagicMock(return_value=ai.EmailSummary("- Priya meets Friday.\n- Reply today.", True))
    monkeypatch.setattr(pages, "fetch_inbox", fetch)
    monkeypatch.setattr(pages, "summarize_email", summarize)
    app = AppTest.from_string("from email_assistant.ui.pages import render_inbox\nrender_inbox()")
    app.run()
    summarize.assert_not_called()
    app.button(key="summarize_1").click().run()
    summarize.assert_called_once_with("Body 1")
    assert set(app.session_state.inbox_summaries) == {"1"}
    assert any("Priya meets" in text.value for text in app.text)
    assert any("16,000" in caption.value for caption in app.caption)
    app.run()
    summarize.assert_called_once()
    fetch.assert_called_once()
    summarize.side_effect = ai.SummaryGenerationError("NVIDIA rate limit or quota reached.")
    app.button(key="summarize_0").click().run()
    assert "quota" in app.error[0].value
    summarize.side_effect = RuntimeError("secret token")
    app.button(key="summarize_0").click().run()
    assert "secret token" not in app.error[0].value + caplog.text
    summarize.side_effect = None
    summarize.return_value = ai.EmailSummary('- <img src="https://example.com/pixel">')
    app.button(key="summarize_0").click().run()
    assert not app.error and not app.exception
    assert any('<img src=' in text.value for text in app.text)
    assert all('<img src=' not in md.value for md in app.markdown)
    app.button[0].click().run()
    assert not app.session_state.inbox_summaries
