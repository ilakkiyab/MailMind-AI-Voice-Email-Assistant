"""Exercise the real Streamlit confirmation UI with mocked delivery."""

from unittest.mock import MagicMock

from streamlit.testing.v1 import AppTest

from email_assistant.email import EmailDeliveryError
from email_assistant.ui import pages


def compose():
    app = AppTest.from_string("from email_assistant.ui.pages import render_compose\nrender_compose()")
    app.run()
    app.text_input(key="recipient").set_value("person@example.com")
    app.text_input(key="subject").set_value("Edited subject")
    app.text_area(key="email_body").set_value("Edited body")
    return app


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def test_confirmation_sends_once_and_survives_rerun(monkeypatch):
    sender = MagicMock(return_value="id")
    monkeypatch.setattr(pages, "send_email", sender)
    app = compose()
    click(app, "Send Email")
    sender.assert_not_called()
    assert any("To: person@example.com\nSubject: Edited subject" == item.value for item in app.text)
    assert any("Edited body" == item.value for item in app.text)
    click(app, "Confirm and send")
    sender.assert_called_once_with("person@example.com", "Edited subject", "Edited body")
    assert any(message.value == "Email sent successfully" for message in app.success)
    assert app.text_input(key="recipient").value == "person@example.com"
    assert app.text_input(key="subject").value == "Edited subject"
    assert app.text_area(key="email_body").value == "Edited body"
    app.run()
    sender.assert_called_once()
    assert not any(button.label == "Confirm and send" for button in app.button)


def test_cancel_and_clear_do_not_send(monkeypatch):
    sender = MagicMock()
    monkeypatch.setattr(pages, "send_email", sender)
    app = compose()
    click(app, "Send Email")
    click(app, "Cancel send")
    assert "pending_email" not in app.session_state
    click(app, "Send Email")
    click(app, "Clear")
    assert "pending_email" not in app.session_state
    sender.assert_not_called()


def test_invalid_form_does_not_offer_confirmation(monkeypatch):
    sender = MagicMock()
    monkeypatch.setattr(pages, "send_email", sender)
    app = compose()
    app.text_input(key="recipient").set_value("invalid")
    click(app, "Send Email")
    assert app.warning
    assert "pending_email" not in app.session_state
    sender.assert_not_called()


def test_error_retains_draft_and_requires_new_confirmation(monkeypatch):
    sender = MagicMock(side_effect=EmailDeliveryError("Gmail unavailable"))
    monkeypatch.setattr(pages, "send_email", sender)
    app = compose()
    click(app, "Send Email")
    click(app, "Confirm and send")
    assert app.error[0].value == "Gmail unavailable"
    assert app.text_area(key="email_body").value == "Edited body"
    assert "pending_email" not in app.session_state
    app.run()
    sender.assert_called_once()


def test_confirmation_uses_preview_snapshot(monkeypatch):
    sender = MagicMock(return_value="id")
    monkeypatch.setattr(pages, "send_email", sender)
    app = compose()
    click(app, "Send Email")
    app.text_input(key="subject").set_value("Unsubmitted change")
    click(app, "Confirm and send")
    sender.assert_called_once_with("person@example.com", "Edited subject", "Edited body")
