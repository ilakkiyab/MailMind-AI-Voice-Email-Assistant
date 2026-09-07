"""Action reminder integration uses synthetic email and temporary local storage."""

from dataclasses import replace
from datetime import date, time
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from email_assistant.ai.actions import ExtractedAction, ActionAnalysis
from email_assistant.storage.reminders import ReminderStore
from email_assistant.ui import action_reminders as ui


EMAIL = SimpleNamespace(id='email-1', subject='Documents', sender='sender@example.test',
                        body='Private body must not be copied', received_at=None)
ACTION = ExtractedAction('Submit documents', 'Deadline', '2099-09-08', '10:30',
                         'Submit required documents.', 'explicit', '08 Sep 2099',
                         '10:30 AM', 'Submit documents')


@pytest.fixture
def store(tmp_path):
    return ReminderStore(tmp_path / 'test.db')


@pytest.mark.parametrize('changes,day,clock', [
    ({}, date(2099, 9, 8), time(10, 30)),
    ({'time': None}, date(2099, 9, 8), None),
    ({'date': None, 'time': None}, None, None),
    ({'date': 'bad', 'time': '25:80'}, None, None),
])
def test_prefill(changes, day, clock):
    draft = ui.action_draft(EMAIL, replace(ACTION, **changes))
    assert draft['date'] == day and draft['time'] == clock
    assert draft['title'] == ACTION.title
    assert EMAIL.subject in draft['description'] and EMAIL.sender in draft['description']
    assert EMAIL.body not in draft['description']


@pytest.mark.parametrize('changes,message', [
    ({'date': None}, 'choose a reminder date'),
    ({'time': None}, 'choose a reminder time'),
    ({'date': date(2000, 1, 1)}, 'future'),
    ({'date': 'bad'}, 'valid reminder date'),
    ({'time': 'bad'}, 'valid reminder date'),
    ({'title': ' '}, 'title'),
])
def test_reject_invalid(store, changes, message):
    draft = ui.action_draft(EMAIL, ACTION)
    draft.update(changes)
    with pytest.raises(ValueError, match=message):
        ui.confirm_action_reminder(store, draft)
    assert not store.list_all() and draft['reminder_id'] is None


def test_success_and_duplicate_guard(store):
    draft = ui.action_draft(EMAIL, ACTION)
    first = ui.confirm_action_reminder(store, draft)
    assert ui.confirm_action_reminder(store, draft) == first
    assert len(store.list_all()) == 1
    assert store.list_all()[0]['title'] == ACTION.title


def test_storage_failure_can_retry(store):
    draft = ui.action_draft(EMAIL, ACTION)
    broken = MagicMock()
    broken.create.side_effect = sqlite3.OperationalError('unavailable')
    with pytest.raises(sqlite3.Error):
        ui.confirm_action_reminder(broken, draft)
    assert draft['reminder_id'] is None
    ui.confirm_action_reminder(store, draft)
    assert len(store.list_all()) == 1


def make_app(monkeypatch, store, items=(ACTION,)):
    monkeypatch.setattr(ui, 'reminder_store', lambda: store)
    app = AppTest.from_string('''
import streamlit as st
from email_assistant.ui.actions import render_actions
for email in st.session_state.test_emails:
    render_actions(email)
''')
    other = SimpleNamespace(**{**vars(EMAIL), 'id': 'email-2'})
    app.session_state.test_emails = [EMAIL, other]
    app.session_state.inbox_actions = {
        e.id: ActionAnalysis(tuple(items), e.id) for e in [EMAIL, other]
    }
    return app.run()


def test_review_edit_success_rerun_and_navigation(monkeypatch, store):
    app = make_app(monkeypatch, store)
    key = ui.action_key(EMAIL.id, ACTION)
    assert not store.list_all()
    app.button(key=key + '_open').click().run()
    assert app.date_input[0].value == date(2099, 9, 8)
    assert app.time_input[0].value == time(10, 30)
    assert not store.list_all()
    app.text_input(key=key + '_title').set_value('Edited title').run()
    app.button(key=key + '_confirm').click().run()
    assert app.success[0].value == 'Reminder created successfully.'
    assert store.list_all()[0]['title'] == 'Edited title'
    app.run()
    assert len(store.list_all()) == 1 and not app.exception
    app.button(key=key + '_view').click().run()
    assert app.session_state.current_page == 'Reminders'


def test_missing_fields_and_storage_error_ui(monkeypatch, store):
    action = replace(ACTION, date=None, time=None)
    app = make_app(monkeypatch, store, [action])
    key = ui.action_key(EMAIL.id, action)
    app.button(key=key + '_open').click().run()
    assert app.date_input[0].value is None and app.time_input[0].value is None
    app.button(key=key + '_confirm').click().run()
    assert 'choose a reminder date' in app.error[0].value
    app.date_input[0].set_value(date(2099, 9, 8)).run()
    app.button(key=key + '_confirm').click().run()
    assert 'choose a reminder time' in app.error[0].value
    app.time_input[0].set_value(time(10, 30)).run()
    monkeypatch.setattr(ui, 'reminder_store', MagicMock(side_effect=sqlite3.OperationalError('secret')))
    app.button(key=key + '_confirm').click().run()
    assert 'storage is unavailable' in app.error[0].value
    assert 'secret' not in app.error[0].value and not app.exception
    monkeypatch.setattr(ui, 'reminder_store', lambda: store)
    app.button(key=key + '_confirm').click().run()
    assert len(store.list_all()) == 1


def test_multiple_actions_email_isolation_reorder_and_hidden_widgets(monkeypatch, store):
    second = replace(ACTION, title='Attend meeting')
    app = make_app(monkeypatch, store, [ACTION, second, ACTION])
    assert len([b for b in app.button if b.label == 'Create Reminder']) == 6
    first_key = ui.action_key(EMAIL.id, ACTION)
    second_key = ui.action_key(EMAIL.id, second)
    app.button(key=first_key + '_open').click().run()
    app.text_input(key=first_key + '_title').set_value('My edit').run()
    app.button(key=second_key + '_open').click().run()
    assert app.text_input(key=second_key + '_title').value == second.title
    emails = app.session_state.test_emails
    app.session_state.test_emails = [emails[1]]
    app.run()
    app.session_state.test_emails = list(reversed(emails))
    app.session_state.inbox_actions[EMAIL.id] = ActionAnalysis((second, ACTION, ACTION), EMAIL.id)
    app.run()
    assert app.text_input(key=first_key + '_title').value == 'My edit'
    app.button(key=first_key + '_confirm').click().run()
    assert len(store.list_all()) == 1
    assert app.text_input(key=second_key + '_title').value == second.title
    assert app.button(key=ui.action_key('email-2', ACTION) + '_open')
    assert app.button(key=ui.action_key(EMAIL.id, ACTION, 1) + '_open')
    assert not app.exception
