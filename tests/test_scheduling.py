from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from email_assistant.email import EmailDeliveryError
from email_assistant.scheduling.service import create_scheduled_email, process_due_emails, local_schedule
from email_assistant.storage.scheduled import ScheduledEmailStore

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
DUE = NOW + timedelta(minutes=1)


@pytest.fixture
def store(tmp_path):
    return ScheduledEmailStore(tmp_path / 'mailmind.db')


def create(store, when=DUE, **kwargs):
    fields = dict(recipient='person@example.com', subject='Subject', body='Body')
    fields.update(kwargs)
    return create_scheduled_email(store, **fields, scheduled_at=when, now=NOW)


def test_create_persists_across_connections(store):
    record_id = create(store)
    row = ScheduledEmailStore(store.path).list_all()[0]
    assert row['id'] == record_id
    assert (row['recipient'], row['subject'], row['body'], row['status']) == ('person@example.com', 'Subject', 'Body', 'Pending')
    assert row['scheduled_at'] == DUE.timestamp()


@pytest.mark.parametrize('when', [NOW, NOW - timedelta(seconds=1), DUE.replace(tzinfo=None)])
def test_future_validation(store, when):
    with pytest.raises(ValueError):
        create(store, when)
    assert not store.list_all()


@pytest.mark.parametrize('fields', [{'recipient': 'invalid'}, {'subject': ' '}, {'body': ''}])
def test_invalid_message(store, fields):
    with pytest.raises(EmailDeliveryError):
        create(store, **fields)
    assert not store.list_all()


def test_cancel_and_delete(store):
    record_id = create(store)
    assert not store.delete(record_id)
    assert store.cancel(record_id)
    assert not store.cancel(record_id)
    sender = Mock()
    process_due_emails(store, now=DUE, sender=sender)
    sender.assert_not_called()
    assert store.list_all()[0]['status'] == 'Cancelled'
    assert store.delete(record_id)
    assert not store.list_all()


def test_due_boundary_and_timezone(store):
    create(store, DUE.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert not store.due(NOW.timestamp())
    assert len(store.due(DUE.timestamp())) == 1


def test_success_and_duplicate_prevention(store):
    record_id = create(store)
    sender = Mock(return_value='gmail-id')
    process_due_emails(store, now=NOW, sender=sender)
    sender.assert_not_called()
    process_due_emails(store, now=DUE, sender=sender)
    process_due_emails(ScheduledEmailStore(store.path), now=DUE, sender=sender)
    sender.assert_called_once_with('person@example.com', 'Subject', 'Body')
    row = store.list_all()[0]
    assert row['status'] == 'Sent' and row['message_id'] == 'gmail-id'
    assert not store.cancel(record_id)
    assert store.delete(record_id)


@pytest.mark.parametrize('error', [EmailDeliveryError('private'), RuntimeError('secret-token')])
def test_failure_no_retry_or_secret_leak(store, error):
    create(store)
    sender = Mock(side_effect=error)
    process_due_emails(store, now=DUE, sender=sender)
    process_due_emails(store, now=DUE, sender=sender)
    sender.assert_called_once()
    row = store.list_all()[0]
    assert row['status'] == 'Failed'
    assert str(error) not in row['error']
    assert 'No automatic retry' in row['error']


def test_unconfirmed_delivery_is_failed(store):
    create(store)
    process_due_emails(store, now=DUE, sender=Mock(return_value=None))
    assert store.list_all()[0]['status'] == 'Failed'


def test_concurrent_workers_send_once(store):
    create(store)
    sender = Mock(return_value='id')
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: process_due_emails(ScheduledEmailStore(store.path), now=DUE, sender=sender), range(4)))
    sender.assert_called_once()


def test_interrupted_claim_never_retried(store):
    record_id = create(store)
    assert store.claim(record_id, DUE.timestamp())
    assert not store.cancel(record_id)
    assert not store.delete(record_id)
    sender = Mock()
    process_due_emails(store, now=DUE + timedelta(minutes=16), sender=sender)
    sender.assert_not_called()
    assert store.list_all()[0]['status'] == 'Failed'


def test_status_write_failure_after_delivery_never_resends(store, monkeypatch):
    import sqlite3
    create(store)
    sender = Mock(return_value='accepted-by-gmail')
    with monkeypatch.context() as patch:
        patch.setattr(store, 'finish', Mock(side_effect=sqlite3.OperationalError('disk full')))
        with pytest.raises(sqlite3.OperationalError):
            process_due_emails(store, now=DUE, sender=sender)
    reopened = ScheduledEmailStore(store.path)
    assert reopened.list_all()[0]['status'] == 'Sending'
    process_due_emails(reopened, now=DUE + timedelta(minutes=16), sender=sender)
    sender.assert_called_once()
    assert reopened.list_all()[0]['status'] == 'Failed'


def test_default_sender_uses_existing_gmail_service(store, monkeypatch):
    from email_assistant.scheduling import service
    create(store)
    sender = Mock(return_value='gmail-id')
    monkeypatch.setattr(service, 'send_email', sender)
    process_due_emails(store, now=DUE)
    sender.assert_called_once_with('person@example.com', 'Subject', 'Body')


def test_local_time_round_trip():
    local = datetime.now().replace(second=0, microsecond=0)
    aware = local_schedule(local.date(), local.time())
    assert aware.tzinfo is not None
    assert datetime.fromtimestamp(aware.timestamp()) == local


def test_ui_create_cancel_delete(store, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from email_assistant.ui import scheduled
    monkeypatch.setattr(scheduled, 'scheduled_store', lambda: store)
    app = AppTest.from_string('from email_assistant.ui.scheduled import render_scheduled\nrender_scheduled()').run()
    app.text_input(key='schedule_recipient').set_value('person@example.com')
    app.text_input(key='schedule_subject').set_value('Subject')
    app.text_area(key='schedule_body').set_value('Body')
    next(b for b in app.button if b.label == 'Schedule email').click().run()
    assert not app.exception
    assert app.success
    assert store.list_all()[0]['status'] == 'Pending'
    next(b for b in app.button if b.label == 'Cancel scheduled email').click().run()
    assert not app.exception
    assert store.list_all()[0]['status'] == 'Cancelled'
    next(b for b in app.button if b.label == 'Delete record').click().run()
    assert not app.exception
    assert not store.list_all()
