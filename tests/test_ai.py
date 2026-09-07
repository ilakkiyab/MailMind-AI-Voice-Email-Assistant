"""Tests for AI-backed email draft generation."""

from types import SimpleNamespace

import pytest

from email_assistant.ai import DraftGenerationError, generate_email_draft


class FakeCompletions:
    def __init__(self, output_text=None, error=None):
        self.output_text = output_text
        self.error = error
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.output_text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def fake_client(output_text=None, error=None):
    completions = FakeCompletions(output_text, error)
    chat = SimpleNamespace(completions=completions)
    return SimpleNamespace(chat=chat), completions


def test_generate_email_draft_returns_subject_and_body():
    client, completions = fake_client(
        '{"subject":"Project update","body":"Hello,\\n\\nThe project is on track.\\n\\nBest regards"}'
    )

    draft = generate_email_draft(
        "Tell the team the project is on track", "Friendly", client=client
    )

    assert draft.subject == "Project update"
    assert "project is on track" in draft.body
    assert completions.request["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert completions.request["stream"] is False
    assert completions.request["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert "friendly tone" in completions.request["messages"][1]["content"]
    assert "exactly two string fields" in completions.request["messages"][1]["content"]


def test_generate_email_draft_rejects_empty_instruction():
    client, _ = fake_client()
    with pytest.raises(DraftGenerationError, match="transcribe or type"):
        generate_email_draft("  ", client=client)


def test_generate_email_draft_rejects_invalid_output():
    client, _ = fake_client("not json")
    with pytest.raises(DraftGenerationError, match="Malformed response"):
        generate_email_draft("Write an update", client=client)


def test_generate_email_draft_rejects_missing_output():
    client, _ = fake_client(None)
    with pytest.raises(DraftGenerationError, match="Malformed response"):
        generate_email_draft("Write an update", client=client)


def test_generate_email_draft_parses_fenced_json_with_intro():
    client, _ = fake_client(
        'Here is the draft:\n```json\n{"Subject":"Status update","Body":"Hello team,\\n\\nAll work is complete."}\n```'
    )

    draft = generate_email_draft("Share the status", client=client)

    assert draft.subject == "Status update"
    assert draft.body.startswith("Hello team")


def test_generate_email_draft_recovers_labeled_plain_text():
    client, _ = fake_client(
        "Subject: Meeting follow-up\n\nEmail Body:\nHello Priya,\n\nThank you for your time."
    )

    draft = generate_email_draft("Thank Priya for the meeting", client=client)

    assert draft.subject == "Meeting follow-up"
    assert draft.body == "Hello Priya,\n\nThank you for your time."


def test_generate_email_draft_recovers_body_without_body_label():
    client, _ = fake_client(
        "Subject: Project timeline\n\nHello,\n\nThe project remains on schedule."
    )

    draft = generate_email_draft("Give a timeline update", client=client)

    assert draft.subject == "Project timeline"
    assert draft.body.startswith("Hello")


@pytest.mark.parametrize(
    "response",
    [
        '{"subject":"","body":"Message"}',
        '{"subject":"Update","body":""}',
        "Subject: Update",
    ],
)
def test_generate_email_draft_rejects_empty_fields(response):
    client, _ = fake_client(response)
    with pytest.raises(DraftGenerationError, match="Malformed response"):
        generate_email_draft("Write an update", client=client)


def test_generate_email_draft_hides_unknown_provider_failure():
    client, _ = fake_client(error=RuntimeError("secret provider detail"))
    with pytest.raises(DraftGenerationError, match="NVIDIA service error") as error:
        generate_email_draft("Write an update", client=client)
    assert "secret provider detail" not in str(error.value)


@pytest.mark.parametrize(
    ("status_code", "category"),
    [
        (401, "Authentication error"),
        (404, "Invalid or unavailable model"),
        (429, "Rate limit error"),
    ],
)
def test_generate_email_draft_categorizes_api_errors(status_code, category):
    error = RuntimeError("sensitive provider detail")
    error.status_code = status_code
    client, _ = fake_client(error=error)

    with pytest.raises(DraftGenerationError, match=category) as caught:
        generate_email_draft("Write an update", client=client)
    assert "sensitive provider detail" not in str(caught.value)


def test_generate_email_draft_categorizes_network_errors():
    client, _ = fake_client(error=TimeoutError("network detail"))
    with pytest.raises(DraftGenerationError, match="Timeout or network error"):
        generate_email_draft("Write an update", client=client)


def test_generate_email_draft_requires_configuration(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setattr("email_assistant.ai._load_environment", lambda: None)
    with pytest.raises(DraftGenerationError, match="not configured"):
        generate_email_draft("Write an update")


def test_nvidia_client_uses_required_endpoint(monkeypatch):
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("openai.OpenAI", fake_openai)
    from email_assistant.ai import _nvidia_client

    _nvidia_client("test-key")

    assert captured == {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "test-key",
        "timeout": 30.0,
        "max_retries": 1,
    }
