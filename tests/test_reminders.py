from datetime import datetime, timedelta, timezone
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from email_assistant.reminders.service import (
    create_reminder, local_reminder_time, new_due_reminders, reminder_section,
)
from email_assistant.storage.reminders import ReminderStore
from email_assistant.storage.scheduled import ScheduledEmailStore

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
DUE = NOW + timedelta(minutes=1)


@pytest.fixture
def store(tmp_path):
    return ReminderStore(tmp_path / 'mailmind.db')


def create(store, when=DUE, **fields):
    return create_reminder(store, fields.get('title', ' Follow up '), fields.get('description', ' Details '), when, now=NOW)


def test_create_and_persistence_with_scheduled_table(store):
    scheduled = ScheduledEmailStore(store.path)
    from email_assistant.email import prepare_email
    scheduled.create(prepare_email('person@example.com', 'Subject', 'Body'), DUE.timestamp())
    record_id = create(store)
    row = ReminderStore(store.path).list_all()[0]
    assert row == dict(id=record_id, title='Follow up', description='Details', scheduled_at=DUE.timestamp(), status='Pending', notification_dismissed=0)
    assert len(scheduled.list_all()) == 1


def test_optional_description_and_sql_text(store):
    create(store, title="'); DROP TABLE reminders;--", description=None)
    assert store.list_all()[0]['description'] == ''


@pytest.mark.parametrize('when', [NOW, NOW - timedelta(seconds=1), DUE.replace(tzinfo=None), None, 'tomorrow', 123])
def test_invalid_times(store, when):
    with pytest.raises(ValueError):
        create(store, when)
    assert not store.list_all()


@pytest.mark.parametrize('fields', [{'title': ''}, {'title': '  '}, {'title': None}, {'title': 123}, {'description': []}])
def test_invalid_fields(store, fields):
    with pytest.raises(ValueError):
        create(store, **fields)
    assert not store.list_all()


def test_due_boundary_timezone_and_sections(store):
    create(store, DUE.astimezone(timezone(timedelta(hours=5, minutes=30))))
    row = store.list_all()[0]
    assert not store.due(NOW.timestamp())
    assert store.due(DUE.timestamp()) == [row]
    assert reminder_section(row, NOW) == 'Upcoming'
    assert reminder_section(row, DUE) == 'Past/Overdue'


def test_complete_persists_and_prevents_notification(store):
    record_id = create(store)
    assert store.complete(record_id)
    assert not store.complete(record_id)
    reopened = ReminderStore(store.path)
    assert reminder_section(reopened.list_all()[0], DUE) == 'Completed'
    assert not new_due_reminders(reopened, set(), now=DUE)


@pytest.mark.parametrize('completed', [False, True])
def test_delete(store, completed):
    record_id = create(store)
    if completed:
        store.complete(record_id)
    assert store.delete(record_id)
    assert not store.delete(record_id)
    assert not ReminderStore(store.path).list_all()
    assert not new_due_reminders(store, set(), now=DUE)


def test_duplicate_notifications_and_new_session(store):
    first = create(store)
    notified = set()
    assert not new_due_reminders(store, notified, now=NOW)
    assert [r['id'] for r in new_due_reminders(store, notified, now=DUE)] == [first]
    assert not new_due_reminders(ReminderStore(store.path), notified, now=DUE)
    second = create(store)
    assert [r['id'] for r in new_due_reminders(store, notified, now=DUE)] == [second]
    assert len(new_due_reminders(store, set(), now=DUE)) == 2


def test_local_time_round_trip_and_invalid_input():
    local = datetime.now().replace(second=0, microsecond=0)
    aware = local_reminder_time(local.date(), local.time())
    assert datetime.fromtimestamp(aware.timestamp()) == local
    for day, clock in [(None, local.time()), (local.date(), None), ('tomorrow', 'noon')]:
        with pytest.raises(ValueError, match='valid reminder'):
            local_reminder_time(day, clock)


def click(app, label):
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception


def test_ui_validation_create_complete_delete(store, monkeypatch):
    from email_assistant.ui import reminders
    monkeypatch.setattr(reminders, 'reminder_store', lambda: store)
    app = AppTest.from_string('from email_assistant.ui.reminders import render_reminders\nrender_reminders()').run()
    click(app, 'Create reminder')
    assert 'title' in app.error[0].value
    app.text_input(key='reminder_title').set_value('Call Alex')
    app.date_input(key='reminder_date').set_value(datetime.now().date() - timedelta(days=1))
    click(app, 'Create reminder')
    assert 'future' in app.error[0].value
    app.date_input(key='reminder_date').set_value(datetime.now().date() + timedelta(days=1))
    click(app, 'Create reminder')
    assert len(store.list_all()) == 1
    assert app.success
    click(app, 'Mark as completed')
    assert store.list_all()[0]['status'] == 'Completed'
    assert next(b for b in app.button if b.label == 'Mark as completed').disabled
    click(app, 'Delete reminder')
    assert not store.list_all()


def test_ui_persistent_alert_dismissal_no_repeat(store, monkeypatch):
    from email_assistant.ui import reminders
    monkeypatch.setattr(reminders, 'reminder_store', lambda: store)
    ids = [store.create(f'Due {i}', 'Details', datetime.now().timestamp() - 1) for i in range(3)]
    app = AppTest.from_string('from email_assistant.ui.reminders import render_reminder_notifications\nrender_reminder_notifications()').run()
    assert not app.exception
    assert [c.value for c in app.caption] == ['🔔 3 reminders due']
    assert not app.warning and not app.text
    assert len(app.button) == 2
    app.run()
    assert len(app.caption) == 1
    click(app, 'Dismiss')
    app.run()
    assert not app.caption and not app.button
    reopened = ReminderStore(store.path)
    monkeypatch.setattr(reminders, 'reminder_store', lambda: reopened)
    fresh = AppTest.from_string('from email_assistant.ui.reminders import render_reminder_notifications\nrender_reminder_notifications()').run()
    assert not fresh.exception and not fresh.caption and not fresh.button
    assert [r['id'] for r in reopened.due(datetime.now().timestamp())] == ids
    assert all(r['status'] == 'Pending' for r in reopened.list_all())
    reopened.create('New due', '', datetime.now().timestamp() - 1)
    fresh.run()
    assert [c.value for c in fresh.caption] == ['🔔 1 reminder due']


def test_dismissal_due_boundary_and_completion_independence(store):
    first = create(store)
    later = create(store, DUE + timedelta(minutes=1))
    store.dismiss_notifications(r['id'] for r in store.due_notifications(DUE.timestamp()))
    reopened = ReminderStore(store.path)
    assert not reopened.due_notifications(DUE.timestamp())
    assert [r['id'] for r in reopened.due_notifications(DUE.timestamp() + 60)] == [later]
    assert len(reopened.due(DUE.timestamp() + 60)) == 2
    assert reopened.complete(first)
    assert reopened.delete(first)
    assert reopened.complete(later)
    assert not reopened.due_notifications(DUE.timestamp() + 60)


def test_existing_database_migration(tmp_path):
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', scheduled_at REAL NOT NULL, status TEXT NOT NULL DEFAULT 'Pending')")
        db.execute("INSERT INTO reminders(title, scheduled_at) VALUES ('Existing', 1)")
    store = ReminderStore(path)
    assert store.due_notifications(2)[0]['title'] == 'Existing'
    store.dismiss_notifications([1])
    assert not ReminderStore(path).due_notifications(2)
    assert store.list_all()[0]['status'] == 'Pending'


def test_dashboard_navigation_and_reminder_controls(store, monkeypatch):
    from email_assistant.ui import app as shell, reminders
    import streamlit as st
    monkeypatch.setattr(reminders, 'reminder_store', lambda: store)
    monkeypatch.setattr(shell, 'start_scheduler', lambda: None)
    monkeypatch.setitem(shell.PAGE_RENDERERS, 'Dashboard', lambda: st.title('Dashboard'))
    store.create('Full title', 'Full description', datetime.now().timestamp() - 1)
    app = AppTest.from_string('from email_assistant.ui.app import run_app\nrun_app()').run()
    assert not app.exception
    assert app.title[0].value == 'Dashboard'
    click(app, 'View Reminders')
    assert app.session_state['current_page'] == 'Reminders'
    assert not any(b.label == 'View Reminders' for b in app.button)
    assert 'Full title' in [t.value for t in app.text]
    assert 'Full description' in [t.value for t in app.text]
    click(app, 'Mark as completed')
    assert store.list_all()[0]['status'] == 'Completed'
    click(app, 'Delete reminder')
    assert not store.list_all()


def test_ui_storage_error(monkeypatch):
    from email_assistant.ui import reminders
    def unavailable():
        raise sqlite3.OperationalError('private details')
    monkeypatch.setattr(reminders, 'reminder_store', unavailable)
    app = AppTest.from_string('from email_assistant.ui.reminders import render_reminders, render_reminder_notifications\nrender_reminder_notifications()\nrender_reminders()').run()
    assert not app.exception
    assert len(app.error) == 2
    assert all('private details' not in e.value for e in app.error)
