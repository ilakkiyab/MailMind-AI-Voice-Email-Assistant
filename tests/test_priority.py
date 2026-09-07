"""Priority contracts and Inbox integration; no live AI or Gmail requests."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from email_assistant.ai import priority as ai
from email_assistant.email.gmail import InboxEmail
from email_assistant.ui import pages, priority as ui


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setattr(ai, "_load_environment", lambda: None)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)


def client(output='{"priority":"HIGH","reason":"Confirm the interview tomorrow."}'):
    fake = MagicMock()
    fake.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=output))])
    return fake


@pytest.mark.parametrize("level,body", [
    ("HIGH", "Confirm tomorrow's interview today."),
    ("MEDIUM", "Academic schedule update for next month."),
    ("LOW", "Our weekly promotional newsletter."),
])
def test_classifications(level, body):
    fake = client(json.dumps({"priority": level, "reason": body}))
    result = ai.classify_email_priority("Sender", "Subject", body, client=fake)
    assert result == ai.EmailPriority(level, body)
    request = fake.chat.completions.create.call_args.kwargs
    assert json.loads(request["messages"][1]["content"])["body"] == body
    assert request["model"] == ai.DEFAULT_MODEL


@pytest.mark.parametrize("output", [None, "", "HIGH", "{}", "[]", "null",
    '{"priority":"HIGH/MEDIUM","reason":"Ambiguous"}',
    '{"priority":["HIGH"],"reason":"Invalid"}',
    '{"priority":"LOW","reason":" "}',
    '{"priority":"LOW","reason":4}',
    '{"priority":"LOW","reason":"OK","extra":"HIGH"}',
    '{"priority":"LOW","reason":"OK"} trailing'])
def test_malformed_response(output):
    with pytest.raises(ai.PriorityClassificationError, match="malformed"):
        ai.classify_email_priority("", "", "Hello", client=client(output))


def test_missing_choices():
    fake = client()
    fake.chat.completions.create.return_value = SimpleNamespace(choices=[])
    with pytest.raises(ai.PriorityClassificationError, match="malformed"):
        ai.classify_email_priority("", "", "Hello", client=fake)


@pytest.mark.parametrize("body", [None, "", " \n", ai.EMPTY_BODY, "<p> </p><script>hidden</script>"])
def test_empty_content(body):
    fake = client()
    with pytest.raises(ai.PriorityClassificationError, match="no readable body"):
        ai.classify_email_priority("Sender", "Subject", body, client=fake)
    fake.chat.completions.create.assert_not_called()


def test_configuration_and_excerpt(monkeypatch):
    with pytest.raises(ai.PriorityClassificationError, match="not configured"):
        ai.classify_email_priority("", "", "Hello")
    fake = client('```json\n{"priority":"LOW","reason":"Newsletter."}\n```')
    factory = MagicMock(return_value=fake)
    monkeypatch.setattr(ai, "_nvidia_client", factory)
    monkeypatch.setenv("NVIDIA_API_KEY", "synthetic-key")
    monkeypatch.setenv("NVIDIA_MODEL", "existing-model")
    result = ai.classify_email_priority("Sender", "Subject", "<p>" + "x" * 17000 + "</p>")
    factory.assert_called_once_with("synthetic-key")
    request = fake.chat.completions.create.call_args.kwargs
    assert request["model"] == "existing-model"
    assert request["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert len(json.loads(request["messages"][1]["content"])["body"]) == 16000
    assert result.truncated


@pytest.mark.parametrize("status,match", [(401, "Authentication"), (403, "Authentication"),
    (429, "quota"), (500, "service error"), (404, "model")])
def test_provider_errors(status, match):
    error = RuntimeError("secret")
    error.status_code = status
    fake = client()
    fake.chat.completions.create.side_effect = error
    with pytest.raises(ai.PriorityClassificationError, match=match) as caught:
        ai.classify_email_priority("", "", "Hello", client=fake)
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("error", [ConnectionError("secret"), TimeoutError("secret")])
def test_network_errors(error):
    fake = client()
    fake.chat.completions.create.side_effect = error
    with pytest.raises(ai.PriorityClassificationError, match="network"):
        ai.classify_email_priority("", "", "Hello", client=fake)


def test_per_email_state_refresh_reorder_and_retry(monkeypatch):
    emails = [InboxEmail(str(i), "Sender", "Subject", datetime.now(timezone.utc), "Preview", f"Body {i}") for i in range(2)]
    fetch = MagicMock(return_value=emails)
    classify = MagicMock(return_value=ai.EmailPriority("HIGH", "Confirm tomorrow.", True))
    monkeypatch.setattr(pages, "fetch_inbox", fetch)
    monkeypatch.setattr(ui, "classify_email_priority", classify)
    app = AppTest.from_string("from email_assistant.ui.pages import render_inbox\nrender_inbox()")
    app.run()
    classify.assert_not_called()
    app.button(key="priority_1").click().run()
    classify.assert_called_once_with("Sender", "Subject", "Body 1", received_at=emails[1].received_at)
    assert set(app.session_state.inbox_priorities) == {"1"}
    assert any("High Priority" in t.value for t in app.text)
    assert any("16,000" in c.value for c in app.caption)
    app.run()
    fetch.return_value = list(reversed(emails))
    app.button[0].click().run()
    classify.assert_called_once()
    assert set(app.session_state.inbox_priorities) == {"1"}
    classify.side_effect = ai.PriorityClassificationError("NVIDIA rate limit or quota reached.")
    app.button(key="priority_0").click().run()
    assert "quota" in app.error[0].value
    assert set(app.session_state.inbox_priorities) == {"1"}
    classify.side_effect = RuntimeError("secret")
    app.button(key="priority_0").click().run()
    assert "secret" not in app.error[0].value
    classify.side_effect = None
    classify.return_value = ai.EmailPriority("LOW", '<img src="https://example.com/pixel">')
    app.button(key="priority_0").click().run()
    assert not app.exception and not app.error
    assert app.session_state.inbox_priorities["1"].priority == "HIGH"
    assert app.session_state.inbox_priorities["0"].priority == "LOW"
    assert any("<img" in t.value for t in app.text)
    assert all("<img" not in m.value for m in app.markdown)
