"""Synthetic provider and Streamlit reply workflow coverage; no real delivery."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from email_assistant.ai import replies as ai
from email_assistant.email.gmail import InboxEmail, EmailDeliveryError
from email_assistant.ui import pages, replies as ui


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setattr(ai, "_load_environment", lambda: None)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)


def client(output="Could you clarify which report you need?"):
    fake = MagicMock()
    fake.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=output))])
    return fake


@pytest.mark.parametrize("tone", ai.TONES)
def test_context_provider_and_tone(monkeypatch, tone):
    fake = client()
    factory = MagicMock(return_value=fake)
    monkeypatch.setattr(ai, "_nvidia_client", factory)
    monkeypatch.setenv("NVIDIA_API_KEY", "synthetic")
    monkeypatch.setenv("NVIDIA_MODEL", "existing-model")
    result = ai.generate_email_reply("Lee <lee@example.com>", "Report", "Which report?", tone)
    factory.assert_called_once_with("synthetic")
    request = fake.chat.completions.create.call_args.kwargs
    assert request["model"] == "existing-model"
    assert tone.lower() in request["messages"][0]["content"]
    assert "Do not invent" in request["messages"][0]["content"]
    assert json.loads(request["messages"][1]["content"]) == dict(sender="Lee <lee@example.com>", subject="Report", body="Which report?", truncated=False)
    assert result.text and not result.truncated


@pytest.mark.parametrize("body", [None, "", "  ", ai.EMPTY_BODY, "<p> </p><script>hidden</script>"])
def test_empty(body):
    fake = client()
    with pytest.raises(ai.ReplyGenerationError, match="no readable body"):
        ai.generate_email_reply("Lee", "Hello", body, client=fake)
    fake.chat.completions.create.assert_not_called()


def test_html_and_long():
    fake = client()
    result = ai.generate_email_reply("Lee", "Hello", "<script>secret</script><p>Lee &amp; Jo</p><div>" + "x" * 20000 + "</div>", client=fake)
    context = json.loads(fake.chat.completions.create.call_args.kwargs["messages"][1]["content"])
    assert result.truncated and len(context["body"]) == ai.MAX_BODY_CHARS
    assert "Lee & Jo" in context["body"] and "secret" not in context["body"]


def test_configuration_and_invalid_tone():
    with pytest.raises(ai.ReplyGenerationError, match="not configured"):
        ai.generate_email_reply("Lee", "Hello", "Body")
    with pytest.raises(ValueError, match="tone"):
        ai.generate_email_reply("Lee", "Hello", "Body", "Unknown")


@pytest.mark.parametrize("error", [TimeoutError("secret"), ConnectionError("secret"), RuntimeError("secret")])
def test_safe_errors(error):
    fake = client()
    fake.chat.completions.create.side_effect = error
    with pytest.raises(ai.ReplyGenerationError) as caught:
        ai.generate_email_reply("Lee", "Hello", "Body", client=fake)
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("output", [None, "", 123])
def test_invalid_output(output):
    with pytest.raises(ai.ReplyGenerationError, match="no usable reply"):
        ai.generate_email_reply("Lee", "Hello", "Body", client=client(output))


@pytest.mark.parametrize("sender,body", [("no-reply@example.com", "Hello"), ("Lee", "Unsubscribe here"), ("Newsletter", "Hi")])
def test_warning(sender, body):
    assert ai.reply_warning(sender, body)
    assert not ai.reply_warning("Lee <lee@example.com>", "Which report?")


def test_ui_isolation_edit_regenerate_clear_review_and_send(monkeypatch):
    emails = [InboxEmail(str(i), "Lee <lee@example.com>", "Re: Report" if i else "Report", datetime.now(timezone.utc), "Preview", f"Body {i}") for i in range(2)]
    monkeypatch.setattr(pages, "fetch_inbox", MagicMock(return_value=emails))
    generate = MagicMock(return_value=ai.EmailReply("Draft", True))
    send = MagicMock()
    monkeypatch.setattr(ui, "generate_email_reply", generate)
    monkeypatch.setattr(ui, "send_email", send)
    app = AppTest.from_string("from email_assistant.ui.pages import render_inbox\nrender_inbox()").run()
    app.selectbox(key="reply_tone_1").select("Friendly").run()
    app.button(key="reply_generate_1").click().run()
    generate.assert_called_once_with(emails[1].sender, "Re: Report", "Body 1", "Friendly")
    app.text_area(key="reply_text_1").input("Edited reply").run()
    app.button(key="reply_generate_0").click().run()
    assert app.text_area(key="reply_text_1").value == "Edited reply"
    app.button(key="reply_clear_0").click().run()
    assert app.session_state.inbox_replies["0"]["text"] == ""
    assert app.session_state.inbox_replies["1"]["text"] == "Edited reply"
    app.button[0].click().run()
    assert app.text_area(key="reply_text_1").value == "Edited reply"
    app.button(key="reply_send_1").click().run()
    send.assert_not_called()
    app.text_area(key="reply_text_1").input("Reviewed edit").run()
    assert "pending" not in app.session_state.inbox_replies["1"]
    app.button(key="reply_send_1").click().run()
    app.button(key="reply_confirm_1").click().run()
    send.assert_called_once_with("lee@example.com", "Re: Report", "Reviewed edit")
    app.run()
    send.assert_called_once()
    generate.side_effect = ai.ReplyGenerationError("Network unavailable")
    app.button(key="reply_regenerate_1").click().run()
    assert app.text_area(key="reply_text_1").value == "Reviewed edit"
    assert "Network" in app.error[0].value
    generate.side_effect = None
    app.button(key="reply_regenerate_1").click().run()
    assert app.text_area(key="reply_text_1").value == "Draft"
    send.side_effect = EmailDeliveryError("Check Gmail Sent before retrying")
    app.button(key="reply_send_1").click().run()
    app.button(key="reply_confirm_1").click().run()
    assert "Check Gmail Sent" in app.error[0].value
    assert "pending" not in app.session_state.inbox_replies["1"]
    assert not app.exception
