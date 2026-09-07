"""Synthetic emails only; all Google access is replaced before Calendar tests run."""
from dataclasses import replace
from datetime import date, time
from unittest.mock import MagicMock
import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response
from streamlit.testing.v1 import AppTest
from email_assistant.calendar import service
from email_assistant.email import gmail
from email_assistant.ui import action_calendar as ui
from email_assistant.ai.actions import ActionAnalysis
from tests.test_action_reminders import EMAIL, ACTION


@pytest.fixture(autouse=True)
def no_google(monkeypatch):
    monkeypatch.setattr(service, 'get_credentials', MagicMock())
    monkeypatch.setattr(service, 'AuthorizedHttp', MagicMock())
    api = MagicMock()
    api.__enter__.return_value = api
    monkeypatch.setattr(service, 'build', MagicMock(return_value=api))
    api.events().insert().execute.side_effect = lambda **kw: {
        'id': api.events().insert.call_args.kwargs['body']['id'],
        'htmlLink': 'https://calendar.google.com/calendar/event?eid=test'}
    return api


def draft():
    value = ui.calendar_draft(EMAIL, ACTION)
    value['end_time'] = time(11, 30)
    return value


@pytest.mark.parametrize('changes,day,clock', [({}, date(2099,9,8), time(10,30)),
    ({'date':None}, None, time(10,30)), ({'time':None}, date(2099,9,8), None)])
def test_prefill(changes, day, clock):
    value = ui.calendar_draft(EMAIL, replace(ACTION, **changes))
    assert value['date'] == day and value['time'] == clock
    assert value['end_time'] is None
    assert EMAIL.subject in value['description'] and EMAIL.sender in value['description']
    assert EMAIL.body not in value['description']


def test_explicit_end_duration():
    assert ui.calendar_draft(EMAIL, replace(ACTION, end_time='12:00', end_time_text='until noon'))['end_time'] == time(12)
    value = ui.calendar_draft(EMAIL, replace(ACTION, duration_minutes=90, duration_text='90 minutes'))
    assert value['end_time'] == time(12)


@pytest.mark.parametrize('changes,message', [({'date':None}, 'date'), ({'time':None}, 'start time'),
    ({'end_time':None}, 'end time'), ({'end_time':time(9)}, 'after'),
    ({'date':date(2000,1,1),'end_date':date(2000,1,1)}, 'past'), ({'title':' '}, 'title')])
def test_validation_no_api(no_google, changes, message):
    value = draft(); value.update(changes)
    with pytest.raises(ValueError, match=message): ui.confirm_calendar(value, 'identity')
    service.get_credentials.assert_not_called()
    assert value['submitted'] is None


def test_create_and_duplicate(no_google):
    value = draft()
    first = ui.confirm_calendar(value, 'identity')
    assert ui.confirm_calendar(value, 'identity') == first
    call = no_google.events().insert.call_args.kwargs
    no_google.events().insert.return_value.execute.assert_called_once_with(num_retries=0)
    assert call['calendarId'] == 'primary' and call['sendUpdates'] == 'none'
    assert 'attendees' not in call['body']
    service.get_credentials.assert_called_once_with([service.CALENDAR_SCOPE], preserve_existing_scopes=True)


def test_uncertain_response_then_conflict(no_google):
    value = draft()
    insert = no_google.events().insert().execute
    insert.side_effect = TimeoutError('secret')
    with pytest.raises(service.CalendarError, match='network'): ui.confirm_calendar(value, 'identity')
    body = value['submitted'].copy()
    insert.side_effect = HttpError(Response({'status':409}), b'secret')
    no_google.events().get().execute.return_value = {'id':body['id']}
    assert ui.confirm_calendar(value, 'identity')['id'] == body['id']
    assert no_google.events().insert.call_args.kwargs['body'] == body
    assert no_google.events().get.call_args.kwargs == {'calendarId':'primary','eventId':body['id']}


@pytest.mark.parametrize('status,content,message', [(403,b'accessNotConfigured','not enabled'),
    (403,b'secret','permission'), (401,b'secret','token'), (500,b'secret','API failed')])
def test_api_failures(no_google, status, content, message):
    no_google.events().insert().execute.side_effect = HttpError(Response({'status':status}), content)
    with pytest.raises(service.CalendarError, match=message) as error: ui.confirm_calendar(draft(), 'id')
    assert 'secret' not in str(error.value)


def test_oauth_failure(no_google):
    service.get_credentials.side_effect = gmail.EmailDeliveryError('Google OAuth permission missing')
    with pytest.raises(service.CalendarError, match='permission'): ui.confirm_calendar(draft(), 'id')
    service.build.assert_not_called()


@pytest.mark.parametrize('url', ['http://calendar.google.com/event','https://evil.test','javascript:alert(1)',
    'https://calendar.google.com.evil.test/', 'https://www.google.com/url?q=evil', 'https://user@calendar.google.com/'])
def test_safe_links(url):
    assert service.safe_event_link(url) is None


def app_for(items=(ACTION,)):
    app = AppTest.from_string('''
import streamlit as st
from email_assistant.ui.actions import render_actions
for email in st.session_state.test_emails:
    render_actions(email)
''')
    other = type(EMAIL)(**{**vars(EMAIL), 'id':'email-2'})
    app.session_state.test_emails = [EMAIL, other]
    app.session_state.inbox_actions = {e.id:ActionAnalysis(tuple(items), e.id) for e in [EMAIL, other]}
    return app.run()


def test_review_edit_confirm_cancel_and_isolation(no_google):
    second = replace(ACTION, title='Meeting')
    app = app_for((ACTION, second, ACTION))
    assert len([b for b in app.button if b.label == 'Add to Calendar']) == 6
    key = ui.calendar_key(EMAIL.id, ACTION)
    app.button(key=key+'_open').click().run()
    app.text_input(key=key+'_title').set_value('Edited event').run()
    app.text_area(key=key+'_description').set_value('Edited details').run()
    app.time_input(key=key+'_end_time').set_value(time(12)).run()
    service.get_credentials.assert_not_called()
    app.button(key=key+'_cancel').click().run()
    service.get_credentials.assert_not_called()
    app.button(key=key+'_open').click().run()
    assert app.text_input(key=key+'_title').value == 'Edited event'
    emails = app.session_state.test_emails
    app.session_state.test_emails = [emails[1]]; app.run()
    app.session_state.test_emails = emails
    app.session_state.inbox_actions[EMAIL.id] = ActionAnalysis((second, ACTION, ACTION), EMAIL.id)
    app.run()
    assert app.text_input(key=key+'_title').value == 'Edited event'
    app.button(key=key+'_confirm').click().run()
    assert app.success[0].value == 'Event added to Google Calendar'
    body = no_google.events().insert.call_args.kwargs['body']
    assert body['summary'] == 'Edited event' and body['description'] == 'Edited details'
    app.run()
    no_google.events().insert().execute.assert_called_once()
    assert app.button(key=ui.calendar_key('email-2', ACTION)+'_open')
    assert app.button(key=ui.calendar_key(EMAIL.id, ACTION, 1)+'_open')
    assert not app.exception


def test_missing_fields_ui(no_google):
    action = replace(ACTION, date=None, time=None)
    app = app_for((action,)); key = ui.calendar_key(EMAIL.id, action)
    app.button(key=key+'_open').click().run()
    assert app.date_input(key=key+'_date').value is None
    assert app.time_input(key=key+'_time').value is None
    app.button(key=key+'_confirm').click().run()
    assert 'date' in app.error[0].value
    app.date_input(key=key+'_date').set_value(date(2099,9,8)).run()
    app.date_input(key=key+'_end_date').set_value(date(2099,9,8)).run()
    app.button(key=key+'_confirm').click().run()
    assert 'start time' in app.error[0].value
    service.get_credentials.assert_not_called()


def test_oauth_reconsent_preserves_gmail(tmp_path, monkeypatch):
    monkeypatch.setattr(gmail, 'PROJECT_ROOT', tmp_path)
    (tmp_path/'credentials.json').touch(); (tmp_path/'token.json').write_text('old token')
    old = MagicMock(valid=True, scopes=gmail.INBOX_SCOPES)
    monkeypatch.setattr(gmail.Credentials, 'from_authorized_user_file', lambda *a:old)
    requested = sorted(gmail.INBOX_SCOPES + [service.CALENDAR_SCOPE])
    new = MagicMock(valid=True, scopes=requested, granted_scopes=requested)
    new.to_json.return_value = 'test-token'
    flow = MagicMock(); flow.run_local_server.return_value = new
    factory = MagicMock(return_value=flow)
    monkeypatch.setattr(gmail.InstalledAppFlow, 'from_client_secrets_file', factory)
    assert gmail.get_credentials([service.CALENDAR_SCOPE], preserve_existing_scopes=True) is new
    assert factory.call_args.args[1] == requested
    new.granted_scopes = gmail.INBOX_SCOPES
    (tmp_path/'token.json').write_text('old token')
    with pytest.raises(gmail.EmailDeliveryError, match='permission missing'):
        gmail.get_credentials([service.CALENDAR_SCOPE], preserve_existing_scopes=True)
    assert (tmp_path/'token.json').read_text() == 'old token'


def test_calendar_token_reuse_and_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr(gmail, 'PROJECT_ROOT', tmp_path)
    (tmp_path/'token.json').touch()
    scopes = gmail.INBOX_SCOPES + [service.CALENDAR_SCOPE]
    creds = MagicMock(valid=True, scopes=scopes, granted_scopes=None)
    creds.to_json.return_value = 'refreshed-test-token'
    monkeypatch.setattr(gmail.Credentials, 'from_authorized_user_file', lambda *a:creds)
    flow = MagicMock()
    monkeypatch.setattr(gmail.InstalledAppFlow, 'from_client_secrets_file', flow)
    assert gmail.get_credentials([service.CALENDAR_SCOPE], preserve_existing_scopes=True) is creds
    creds.refresh.assert_not_called()
    creds.valid = False; creds.expired = True; creds.refresh_token = 'test-only'
    creds.refresh.side_effect = lambda request:setattr(creds, 'valid', True)
    assert gmail.get_credentials([service.CALENDAR_SCOPE], preserve_existing_scopes=True) is creds
    creds.refresh.assert_called_once()
    flow.assert_not_called()
    assert (tmp_path/'token.json').read_text() == 'refreshed-test-token'


def test_error_ui_preserves_editable_draft(no_google):
    app = app_for(); key = ui.calendar_key(EMAIL.id, ACTION)
    app.button(key=key+'_open').click().run()
    app.time_input(key=key+'_end_time').set_value(time(12)).run()
    no_google.events().insert().execute.side_effect = HttpError(Response({'status':403}), b'secret')
    app.button(key=key+'_confirm').click().run()
    assert 'permission' in app.error[0].value and 'secret' not in app.error[0].value
    app.text_input(key=key+'_title').set_value('Corrected').run()
    no_google.events().insert().execute.side_effect = lambda **kw: {
        'id':no_google.events().insert.call_args.kwargs['body']['id']}
    app.button(key=key+'_confirm').click().run()
    assert app.success[0].value == 'Event added to Google Calendar'
    assert no_google.events().insert.call_args.kwargs['body']['summary'] == 'Corrected'
    assert not app.exception


def test_uncertain_payload_cannot_change(no_google):
    value = draft()
    no_google.events().insert().execute.side_effect = TimeoutError()
    with pytest.raises(service.CalendarError): ui.confirm_calendar(value, 'id')
    value['title'] = 'Changed after timeout'
    with pytest.raises(ValueError, match='previous attempt'): ui.confirm_calendar(value, 'id')
    no_google.events().insert.return_value.execute.assert_called_once()


@pytest.mark.parametrize('kind', ['Meeting', 'Interview', 'Appointment', 'Deadline', 'Task',
    'Document Submission', 'Payment Deadline', 'Application Deadline'])
@pytest.mark.parametrize('has_schedule', [True, False])
def test_inbox_extract_button_shows_calendar_for_every_action(no_google, monkeypatch, kind, has_schedule):
    from datetime import datetime, timezone
    from email_assistant.email.gmail import InboxEmail
    from email_assistant.ui import actions, pages
    email = InboxEmail('visibility-email', 'sender@example.test', 'Project review meeting',
        datetime(2026, 9, 7, tzinfo=timezone.utc), 'Please attend the project review.',
        'Please attend the project review meeting on 15 October 2099 from 10:00 AM to 11:00 AM IST.')
    action = replace(ACTION, type=kind, date=ACTION.date if has_schedule else None,
                     time=ACTION.time if has_schedule else None)
    monkeypatch.setattr(pages, 'fetch_inbox', MagicMock(return_value=[email]))
    extract = MagicMock(return_value=ActionAnalysis((action,), email.id))
    monkeypatch.setattr(actions, 'extract_email_actions', extract)
    app = AppTest.from_string('from email_assistant.ui.pages import render_inbox\nrender_inbox()').run()
    assert not [b for b in app.button if b.label == 'Add to Calendar']
    assert any('select Extract Actions first' in c.value for c in app.caption)
    app.button(key='actions_' + email.id).click().run()
    key = ui.calendar_key(email.id, action)
    assert app.button(key=key + '_open').label == 'Add to Calendar'
    app.button(key=key + '_open').click().run()
    assert any('Review Calendar Event' in m.value for m in app.markdown)
    assert not app.exception
    service.get_credentials.assert_not_called()
    service.build.assert_not_called()


def test_empty_extraction_explains_missing_calendar_button(no_google, monkeypatch):
    from email_assistant.ui import actions
    app = app_for(())
    assert not [b for b in app.button if b.label == 'Add to Calendar']
    assert any('Add to Calendar appears only when an action is detected' in c.value for c in app.caption)
    monkeypatch.setattr(actions, 'extract_email_actions', MagicMock(side_effect=actions.ActionExtractionError('Extraction unavailable.')))
    app.button(key='actions_' + EMAIL.id).click().run()
    assert app.error[0].value == 'Extraction unavailable.'
    assert not [b for b in app.button if b.label == 'Add to Calendar']
    service.get_credentials.assert_not_called()
    service.build.assert_not_called()
