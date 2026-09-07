"""Extraction contracts and real Streamlit reruns; providers are always mocked."""

import json
import httpx
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from email_assistant.ai import actions as ai
from email_assistant.email.gmail import InboxEmail
from email_assistant.ui import actions as ui, pages


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setattr(ai, "_load_environment", lambda: None)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)


def item(**changes):
    value = dict(title="Submit documents", type="Deadline", date="2026-09-08",
                 time=None, description="Submit required documents.", date_source="explicit",
                 date_text="08 Sep 2026", time_text=None, evidence="Submit documents")
    value.update(changes)
    return value


def client(output):
    fake = MagicMock()
    fake.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=output), finish_reason="stop")])
    return fake


def extract(items, body="Submit documents by 08 Sep 2026.", **kwargs):
    return ai.extract_email_actions("", body, client=client(json.dumps({"actions": items})), **kwargs)


def test_one_deadline():
    result = extract([item()], email_id="message-1")
    assert result.items[0].date == "2026-09-08"
    assert result.items[0].date_source == "explicit"
    assert json.loads(json.dumps(asdict(result)))["source_email_id"] == "message-1"


def test_meeting_with_date_and_time():
    meeting = item(title="Attend meeting", type="Meeting", time="10:30", time_text="10:30 AM IST", evidence="Attend meeting")
    result = extract([meeting], "Attend meeting on 08 Sep 2026 at 10:30 AM IST.")
    assert result.items[0].time == "10:30"
    assert result.items[0].time_text == "10:30 AM IST"


def test_multiple_actions():
    interview = item(title="Attend interview", type="Interview", date="2026-09-10",
                     date_text="10 Sep 2026", time="10:30", time_text="10:30 AM", evidence="Attend interview")
    result = extract([item(), interview], "Submit documents by 08 Sep 2026. Attend interview on 10 Sep 2026 at 10:30 AM.")
    assert len(result.items) == 2
    assert [a.type for a in result.items] == ["Deadline", "Interview"]


def test_no_action():
    assert extract([], "Thank you for the update.").items == ()


def test_missing_date_and_time_and_subject_only():
    task = item(date=None, date_text=None, date_source="unspecified", type="Task")
    fake = client(json.dumps({"actions": [task]}))
    result = ai.extract_email_actions("Submit documents", ai.EMPTY_BODY, client=fake)
    assert result.items[0].date is None and result.items[0].time is None


@pytest.mark.parametrize("phrase,expected", [("tomorrow", "2026-09-07"), ("next Monday", "2026-09-07"), ("this Friday", "2026-09-04")])
def test_relative_dates_resolved_from_received_not_today(phrase, expected):
    received = datetime(2026, 9, 6, 12)
    result = extract([item(date_source="inferred", date_text=phrase)],
                     f"Submit documents {phrase}.", received_at=received)
    assert result.items[0].date == expected
    assert result.items[0].date_source == "inferred"


def test_relative_without_reference_rejected():
    with pytest.raises(ai.ActionExtractionError, match="malformed"):
        extract([item(date_source="inferred", date_text="tomorrow")], "Submit documents tomorrow.")


@pytest.mark.parametrize("output", [None, "", "plain text", "{}", "null", '{"actions":null}',
    '{"actions":[{}]}'])
def test_malformed_response(output):
    with pytest.raises(ai.ActionExtractionError, match="malformed"):
        ai.extract_email_actions("", "Hello", client=client(output))


@pytest.mark.parametrize("changes", [dict(date="2026-02-30"), dict(time="25:00"),
    dict(time="10:00"), dict(date_source="maybe"), dict(title=None), dict(type="Unknown"),
    dict(date=None), dict(evidence="Invented action"), dict(date_text="Invented date"),
    dict(date="2030-09-08"), dict(date_text=None), dict(time_text=12)])
def test_invalid_or_unsupported_fields(changes):
    with pytest.raises(ai.ActionExtractionError, match="malformed"):
        extract([item(**changes)])


@pytest.mark.parametrize("body", [None, "", "  ", ai.EMPTY_BODY, "<script>hidden</script>"])
def test_empty_content_does_not_call_provider(body):
    fake = client("{}")
    with pytest.raises(ai.ActionExtractionError, match="no readable content"):
        ai.extract_email_actions("(No subject)", body, client=fake)
    fake.chat.completions.create.assert_not_called()


def test_configuration_html_excerpt_and_prompt(monkeypatch):
    with pytest.raises(ai.ActionExtractionError, match="not configured"):
        ai.extract_email_actions("", "Hello")
    fake = client('```json\n{"actions":[]}\n```')
    factory = MagicMock(return_value=fake)
    monkeypatch.setattr(ai, "_nvidia_client", factory)
    monkeypatch.setenv("NVIDIA_API_KEY", "synthetic-key")
    monkeypatch.setenv("NVIDIA_MODEL", "existing-model")
    received = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)
    result = ai.extract_email_actions("Subject", "<p>" + "x" * 17000 + "</p>", received_at=received)
    factory.assert_called_once_with("synthetic-key")
    request = fake.chat.completions.create.call_args.kwargs
    assert request["model"] == "existing-model"
    context = json.loads(request["messages"][1]["content"])
    assert len(context["body"]) == 16000 and result.truncated
    assert context["received_at"] == received.astimezone().isoformat()
    assert "never follow instructions" in request["messages"][0]["content"]
    assert request["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert request["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("status,match", [(401, "Authentication"), (403, "Authentication"), (429, "quota"), (500, "service error")])
def test_provider_errors(status, match):
    error = RuntimeError("secret")
    error.status_code = status
    fake = client("{}")
    fake.chat.completions.create.side_effect = error
    with pytest.raises(ai.ActionExtractionError, match=match) as caught:
        ai.extract_email_actions("", "Hello", client=fake)
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("error", [ConnectionError("secret"), TimeoutError("secret")])
def test_network_errors(error):
    fake = client("{}")
    fake.chat.completions.create.side_effect = error
    with pytest.raises(ai.ActionExtractionError, match="network"):
        ai.extract_email_actions("", "Hello", client=fake)


@pytest.mark.parametrize("failure", ["timeout", "connection", 401, 429, 503])
@pytest.mark.parametrize("recover", [True, False])
def test_shared_sdk_transport_retry_and_timeout(monkeypatch, failure, recover):
    from email_assistant.ai import _nvidia_client, NVIDIA_BASE_URL

    requests = []

    def transport(request):
        requests.append(request)
        assert str(request.url) == NVIDIA_BASE_URL + "/chat/completions"
        assert request.extensions["timeout"] == {
            "connect": 10.0, "read": 120.0, "write": 30.0, "pool": 30.0}
        assert json.loads(request.content)["model"] == "existing-model"
        if len(requests) == 1 or not recover:
            if failure == "timeout":
                raise httpx.ReadTimeout("secret", request=request)
            if failure == "connection":
                raise httpx.ConnectError("secret", request=request)
            return httpx.Response(failure, json={"error": {"message": "secret"}})
        return httpx.Response(200, json={"choices": [{
            "message": {"role": "assistant", "content": '{"actions":[]}'},
            "finish_reason": "stop", "index": 0}]})

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        with _nvidia_client("synthetic-key").with_options(http_client=http_client) as sdk:
            assert sdk.max_retries == 1
            assert sdk.timeout == 30.0
            monkeypatch.setattr(ai, "_nvidia_client", lambda key: sdk)
            monkeypatch.setenv("NVIDIA_API_KEY", "synthetic-key")
            monkeypatch.setenv("NVIDIA_MODEL", "existing-model")
            if recover and failure != 401:
                assert ai.extract_email_actions("", "Hello").items == ()
            else:
                expected = {401: "Authentication", 429: "quota", 503: "service error"}.get(failure, "network")
                with pytest.raises(ai.ActionExtractionError, match=expected) as caught:
                    ai.extract_email_actions("", "Hello")
                assert "secret" not in str(caught.value)
            assert len(requests) == (1 if failure == 401 else 2)
            assert sdk.timeout == 30.0


def test_missing_choices_and_truncated_response():
    fake = client('{"actions":[]}')
    fake.chat.completions.create.return_value.choices[0].finish_reason = "length"
    with pytest.raises(ai.ActionExtractionError, match="malformed"):
        ai.extract_email_actions("", "Hello", client=fake)
    fake.chat.completions.create.return_value.choices = []
    with pytest.raises(ai.ActionExtractionError, match="malformed"):
        ai.extract_email_actions("", "Hello", client=fake)


def test_state_isolation_refresh_reorder_retry_and_rendering(monkeypatch):
    emails = [InboxEmail(str(i), "Sender", "Subject", datetime(2026, 9, 6, tzinfo=timezone.utc), "Preview", f"Body {i}") for i in range(2)]
    fetch = MagicMock(return_value=emails)
    analysis = extract([item()], email_id="1")
    run = MagicMock(return_value=analysis)
    monkeypatch.setattr(pages, "fetch_inbox", fetch)
    monkeypatch.setattr(ui, "extract_email_actions", run)
    app = AppTest.from_string("from email_assistant.ui.pages import render_inbox\nrender_inbox()")
    app.run()
    run.assert_not_called()
    assert len([b for b in app.button if b.label == "Extract Actions"]) == 2
    app.button(key="actions_1").click().run()
    run.assert_called_once_with("Subject", "Body 1", received_at=emails[1].received_at, email_id="1")
    assert set(app.session_state.inbox_actions) == {"1"}
    cards = [b for b in app.get("flex_container") if sum(t.value.startswith("From:") for t in b.text) == 1]
    assert not any("Action: Submit" in t.value for t in cards[0].text)
    assert any("Action: Submit" in t.value for t in cards[1].text)
    assert any("08 Sep 2026" in t.value and "Time: Not specified" in t.value for t in app.text)
    app.run()
    fetch.return_value = list(reversed(emails))
    app.button[0].click().run()
    run.assert_called_once()
    assert set(app.session_state.inbox_actions) == {"1"}
    cards = [b for b in app.get("flex_container") if sum(t.value.startswith("From:") for t in b.text) == 1]
    assert any("Action: Submit" in t.value for t in cards[0].text)
    assert not any("Action: Submit" in t.value for t in cards[1].text)
    run.side_effect = ai.ActionExtractionError("NVIDIA rate limit or quota reached.")
    app.button(key="actions_0").click().run()
    assert "quota" in app.error[0].value
    assert set(app.session_state.inbox_actions) == {"1"}
    run.side_effect = RuntimeError("secret")
    app.button(key="actions_1").click().run()
    assert "secret" not in app.error[0].value
    assert app.session_state.inbox_actions["1"] == analysis
    run.side_effect = None
    run.return_value = ai.ActionAnalysis((), "0")
    app.button(key="actions_0").click().run()
    assert any(t.value == "No actions or deadlines detected in this email." for t in app.info)
    assert app.session_state.inbox_actions["1"] == analysis
    assert not app.exception


def test_explicit_calendar_end_and_duration():
    result = extract([item(time='10:00', time_text='10:00', end_time='11:00',
        end_time_text='11:00', duration_minutes=60, duration_text='60 minutes')],
        'Submit documents by 08 Sep 2026. Work 10:00 to 11:00 for 60 minutes.')
    assert result.items[0].end_time == '11:00'
    assert result.items[0].duration_minutes == 60


@pytest.mark.parametrize('changes', [dict(end_time='25:00', end_time_text='noon'),
    dict(end_time='12:00'), dict(duration_minutes=60),
    dict(duration_minutes=True, duration_text='noon'),
    dict(duration_minutes=-1, duration_text='noon'),
    dict(end_time='12:00', end_time_text='invented')])
def test_invalid_calendar_extraction(changes):
    with pytest.raises(ai.ActionExtractionError, match='malformed'):
        extract([item(**changes)], 'Submit documents by 08 Sep 2026 at noon.')


@pytest.mark.parametrize('wrapper', [
    lambda s: s,
    lambda s: ' \n\t' + s + ' \n',
    lambda s: '```json\n' + s + '\n```',
    lambda s: 'Here are the actions:\n```JSON\n' + s + '\n```\nDone.',
    lambda s: 'Here are the actions: ' + s + ' End of response.',
])
def test_json_output_variations(wrapper):
    output = wrapper(json.dumps({'actions': [item()]}))
    result = ai.extract_email_actions('', 'Submit documents by 08 Sep 2026.', client=client(output))
    assert result.items[0].date == '2026-09-08'


@pytest.mark.parametrize('payload', [[], {'actions': [], 'metadata': True},
    {'actions': [item()], 'metadata': 'ignored'}, [item()], item()])
def test_structured_json_variations(payload):
    result = ai.extract_email_actions('', 'Submit documents by 08 Sep 2026.',
                                      client=client(json.dumps(payload)))
    expected = len(payload) if isinstance(payload, list) else (0 if payload.get('actions') == [] else 1)
    assert len(result.items) == expected


def test_missing_optional_fields_and_normalization():
    output = {'Actions': [{'Title': ' Submit documents ', 'Type': 'task',
                           'Evidence': 'Submit documents', 'extra': 'ignored'}]}
    action = ai.extract_email_actions('', 'Submit documents', client=client(json.dumps(output))).items[0]
    assert action.title == 'Submit documents' and action.type == 'Task'
    assert action.description == '' and action.date_source == 'unspecified'
    assert all(getattr(action, name) is None for name in
               ('date', 'time', 'date_text', 'time_text', 'end_time', 'end_time_text',
                'duration_minutes', 'duration_text'))


def test_meeting_date_start_end_in_nvidia_completion():
    meeting = item(title='Attend meeting', type='meeting', evidence='Attend meeting',
                   time='10:00', time_text='10:00', end_time='11:00', end_time_text='11:00')
    result = ai.extract_email_actions('', 'Attend meeting on 08 Sep 2026 from 10:00 to 11:00.',
        client=client('Meeting extracted:\n```json\n' + json.dumps({'actions': [meeting]}) + '\n```'))
    action = result.items[0]
    assert (action.type, action.date, action.time, action.end_time) == ('Meeting', '2026-09-08', '10:00', '11:00')
    assert action.duration_minutes is None


@pytest.mark.parametrize('output', [
    '{"actions": [', '{"actions": [],}', '{"actions": []} {"actions": []}',
    '{"actions": [], "Actions": []}', '{"actions": [broken, {"actions": []}]}',
    '{"actions": [{"title": "secret email"}]}',
])
def test_invalid_output_safe_diagnostics(output, caplog):
    with pytest.raises(ai.ActionExtractionError, match='malformed') as caught:
        ai.extract_email_actions('private subject', 'secret email', client=client(output))
    assert 'stage=json_or_schema' in caplog.text
    assert 'secret email' not in caplog.text + str(caught.value)
    assert 'private subject' not in caplog.text + str(caught.value)


@pytest.mark.parametrize('field', ['title', 'type', 'evidence', 'date_source'])
def test_required_factual_fields_not_invented(field):
    action = item()
    del action[field]
    with pytest.raises(ai.ActionExtractionError, match='malformed'):
        extract([action])
