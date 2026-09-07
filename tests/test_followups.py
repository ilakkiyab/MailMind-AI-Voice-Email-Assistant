from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
from streamlit.testing.v1 import AppTest
from email_assistant.email import followups as service
from email_assistant.ui import followups as ui
from email_assistant.ai import followups as ai

NOW = datetime.now(timezone.utc)


def message(id='s1', thread='t1', days=4, **kwargs):
    return replace(service.SentMessage(id, thread, 'Me <me@example.com>', ('lee@example.com',),
                   'Report', NOW - timedelta(days=days), 'Could you review the report?', True, rfc_message_id='<s@example.com>'), **kwargs)


def detect(items, threshold=3):
    return service.detect_followups(items, ['me@example.com'], threshold, NOW)


def test_unreplied():
    assert detect([message()])[0].status == 'Follow-up Needed'


@pytest.mark.parametrize('days,status', [(2, 'Waiting'), (3, 'Follow-up Needed'), (4, 'Follow-up Needed')])
def test_threshold(days, status):
    assert detect([message(days=days)])[0].status == status


def test_exact_boundary():
    m = message(sent_at=NOW - timedelta(days=3) + timedelta(seconds=1))
    assert detect([m])[0].status == 'Waiting'


def test_replied():
    reply = message('r1', days=1, sender='Lee <lee@example.com>', sent=False)
    assert detect([message(), reply])[0].status == 'Replied'


@pytest.mark.parametrize('sender,sent', [('me@example.com', False), ('alias@example.com', True)])
def test_own_not_reply(sender, sent):
    own = message('own', days=1, sender=sender, sent=sent)
    assert detect([message(), own])[0].status != 'Replied'


def test_duplicate_thread_latest_outbound_resets_wait():
    old_reply = message('r', days=2, sent=False, sender='lee@example.com')
    latest = message('s2', days=1)
    rows = detect([message(), message(), old_reply, latest])
    assert len(rows) == 1 and rows[0].message.id == 's2' and rows[0].status == 'Waiting'


@pytest.mark.parametrize('changes', [dict(automated=True), dict(recipients=('no-reply@example.com',)), dict(body='FYI, report attached.'), dict(body='Thanks.\nOn Monday Lee wrote:\nCould you review?'), dict(body='Newsletter: unsubscribe here?')])
def test_noise(changes):
    assert detect([message(**changes)]) == []


def test_unrelated_or_automated_reply():
    for reply in [message('r', days=1, sender='other@example.com', sent=False),
                  message('r', days=1, sender='lee@example.com', sent=False, automated=True)]:
        assert detect([message(), reply])[0].status == 'Follow-up Needed'


def test_gmail_read_and_dedup(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(service.gmail, 'get_credentials', MagicMock())
    monkeypatch.setattr(service.gmail, 'AuthorizedHttp', MagicMock())
    monkeypatch.setattr(service.gmail, 'build', MagicMock(return_value=fake))
    users = fake.__enter__.return_value.users.return_value
    users.getProfile.return_value.execute.return_value = {'emailAddress': 'me@example.com'}
    users.threads.return_value.list.return_value.execute.return_value = {'threads': [{'id':'t1'}, {'id':'t1'}]}
    users.threads.return_value.get.return_value.execute.return_value = {'messages': [{'id':'s1'}]}
    monkeypatch.setattr(service, 'parse_message', lambda r, t: message())
    account, messages = service.fetch_sent_threads()
    assert len(messages) == 1 and account == 'me@example.com'
    users.threads.return_value.get.assert_called_once()
    users.messages.return_value.send.assert_not_called()
    service.gmail.get_credentials.assert_called_once_with(service.gmail.INBOX_SCOPES, preserve_existing_scopes=True)


def test_gmail_errors_safe(monkeypatch):
    monkeypatch.setattr(service.gmail, 'get_credentials', MagicMock(side_effect=RuntimeError('secret')))
    with pytest.raises(service.FollowupError, match='Could not load') as exc:
        service.fetch_sent_threads()
    assert 'secret' not in str(exc.value)


def test_ai_reuses_provider(monkeypatch):
    provider = MagicMock(return_value=MagicMock(body='Following up on the report.'))
    monkeypatch.setattr(ai, 'generate_email_draft', provider)
    assert ai.generate_followup(message()) == 'Following up on the report.'
    assert 'original_sent_body' in provider.call_args.args[0]


def test_ui_isolation_confirmation_and_edits(monkeypatch):
    monkeypatch.setattr(ui, 'fetch_sent_threads', lambda: ('me@example.com', [message(), message('s2', 't2')]))
    monkeypatch.setattr(ui, 'generate_followup', lambda m: 'Draft ' + m.id)
    send = MagicMock()
    monkeypatch.setattr(ui, 'send_email', send)
    app = AppTest.from_string('from email_assistant.ui.followups import render_followups\nrender_followups()').run()
    a, b = 'me@example.com:t1:s1', 'me@example.com:t2:s2'
    app.button(key='generate_' + a).click().run()
    app.button(key='generate_' + b).click().run()
    assert app.text_area(key='text_' + a).value == 'Draft s1'
    assert app.text_area(key='text_' + b).value == 'Draft s2'
    app.button(key='send_' + a).click().run()
    send.assert_not_called()
    app.text_area(key='text_' + a).input('Edited').run()
    assert not any(x.key == 'confirm_' + a for x in app.button)
    app.button(key='send_' + a).click().run()
    app.button(key='cancel_' + a).click().run()
    send.assert_not_called()
    app.button(key='send_' + a).click().run()
    app.button(key='confirm_' + a).click().run()
    send.assert_called_once_with('lee@example.com', 'Re: Report', 'Edited', thread_id='t1', in_reply_to='<s@example.com>')
    app.run()
    assert send.call_count == 1 and not app.exception


def test_ui_errors(monkeypatch):
    monkeypatch.setattr(ui, 'fetch_sent_threads', MagicMock(side_effect=service.FollowupError('Unable to read Gmail')))
    app = AppTest.from_string('from email_assistant.ui.followups import render_followups\nrender_followups()').run()
    assert app.error and not app.exception

def test_threaded_send_headers(monkeypatch):
    import base64
    from email import policy
    from email.parser import BytesParser
    gmail = service.gmail
    monkeypatch.setattr(gmail, 'get_credentials', MagicMock())
    monkeypatch.setattr(gmail, 'AuthorizedHttp', MagicMock())
    fake = MagicMock()
    monkeypatch.setattr(gmail, 'build', MagicMock(return_value=fake))
    sender = fake.__enter__.return_value.users.return_value.messages.return_value.send
    sender.return_value.execute.return_value = {'id': 'sent'}
    gmail.send_email('lee@example.com', 'Re: Report', 'Following up', thread_id='t1', in_reply_to='<original@example.com>')
    payload = sender.call_args.kwargs['body']
    mime = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(payload['raw']))
    assert payload['threadId'] == 't1'
    assert mime['In-Reply-To'] == mime['References'] == '<original@example.com>'
    sender.return_value.execute.assert_called_once_with(num_retries=0)


def test_stale_reply_blocks_send(monkeypatch):
    fetch = MagicMock(return_value=('me@example.com', [message()]))
    monkeypatch.setattr(ui, 'fetch_sent_threads', fetch)
    monkeypatch.setattr(ui, 'generate_followup', lambda m: 'Draft')
    send = MagicMock()
    monkeypatch.setattr(ui, 'send_email', send)
    app = AppTest.from_string('from email_assistant.ui.followups import render_followups\nrender_followups()').run()
    identity = 'me@example.com:t1:s1'
    app.button(key='generate_' + identity).click().run()
    app.button(key='send_' + identity).click().run()
    fetch.return_value = ('me@example.com', [message(), message('r', days=1, sender='lee@example.com', sent=False)])
    app.button(key='confirm_' + identity).click().run()
    send.assert_not_called()
    assert app.warning and not app.exception

def test_full_thread_fetch_avoids_per_message_calls(monkeypatch):
    import base64
    fake = MagicMock()
    monkeypatch.setattr(service.gmail, 'get_credentials', MagicMock())
    monkeypatch.setattr(service.gmail, 'AuthorizedHttp', MagicMock())
    monkeypatch.setattr(service.gmail, 'build', MagicMock(return_value=fake))
    users = fake.__enter__.return_value.users.return_value
    users.getProfile.return_value.execute.return_value = {'emailAddress': 'me@example.com'}
    users.threads.return_value.list.return_value.execute.return_value = {'threads': [{'id': 't1'}]}
    def resource(id, sender, days, labels):
        return {'id': id, 'internalDate': str(int((NOW-timedelta(days=days)).timestamp()*1000)), 'labelIds': labels,
                'payload': {'headers': [{'name': 'From', 'value': sender}, {'name': 'To', 'value': 'lee@example.com'},
                                       {'name': 'Subject', 'value': 'Report'}, {'name': 'Message-ID', 'value': '<test@example.com>'},
                                       {'name': 'Content-Type', 'value': 'text/plain; charset=utf-8'},
                                       {'name': 'Content-Transfer-Encoding', 'value': 'base64'}],
                            'body': {'data': base64.urlsafe_b64encode('Could you review café?'.encode()).decode()}}}
    users.threads.return_value.get.return_value.execute.return_value = {'messages': [resource('s', 'me@example.com', 4, ['SENT']), resource('r', 'lee@example.com', 1, ['INBOX'])]}
    account, messages = service.fetch_sent_threads()
    assert messages[0].body == 'Could you review café?'
    assert messages[0].rfc_message_id == '<test@example.com>'
    assert detect(messages)[0].status == 'Replied'
    users.threads.return_value.get.assert_called_once_with(userId='me', id='t1', format='full')
    users.messages.assert_not_called()


@pytest.mark.parametrize('status,reason,retries', [(403,'rateLimitExceeded',3),(403,'userRateLimitExceeded',3),(429,'unclassified',3),(403,'insufficientPermissions',0)])
def test_http_diagnostic_and_bounded_retry(monkeypatch, caplog, status, reason, retries):
    import json
    from httplib2 import Response
    error = service.gmail.HttpError(Response({'status': str(status)}), json.dumps({'error': {'message': 'PRIVATE subject token URL', 'errors': [{'reason': reason}]}}).encode())
    fake = MagicMock()
    monkeypatch.setattr(service.gmail, 'get_credentials', MagicMock())
    monkeypatch.setattr(service.gmail, 'AuthorizedHttp', MagicMock())
    monkeypatch.setattr(service.gmail, 'build', MagicMock(return_value=fake))
    sleep = MagicMock()
    monkeypatch.setattr(service.time, 'sleep', sleep)
    users = fake.__enter__.return_value.users.return_value
    users.getProfile.return_value.execute.return_value = {'emailAddress': 'me@example.com'}
    users.threads.return_value.list.return_value.execute.return_value = {'threads': [{'id':'t'}]}
    execute = users.threads.return_value.get.return_value.execute
    execute.side_effect = error
    with pytest.raises(service.FollowupError) as caught:
        service.fetch_sent_threads()
    assert 'users.threads.get (full)' in str(caught.value)
    assert f'HTTP {status} ({reason})' in str(caught.value)
    assert execute.call_count == retries + 1 and sleep.call_count == retries
    assert 'PRIVATE' not in str(caught.value) + caplog.text


def test_rate_limit_recovers(monkeypatch):
    from httplib2 import Response
    request = MagicMock()
    request.execute.side_effect = [service.gmail.HttpError(Response({'status':'403'}), b'{"error":{"errors":[{"reason":"rateLimitExceeded"}]}}'), {'messages': []}]
    monkeypatch.setattr(service.time, 'sleep', MagicMock())
    assert service._execute(request, 'users.threads.get (full)') == {'messages': []}
    assert request.execute.call_count == 2
