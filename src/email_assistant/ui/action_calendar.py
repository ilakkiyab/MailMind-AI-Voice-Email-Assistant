"""Per-email, per-action Calendar review; no creation outside confirmation."""

from datetime import date, datetime, timedelta
import streamlit as st

from email_assistant.calendar.service import CalendarError, create_event, event_body
from .action_reminders import action_key, action_draft


def calendar_key(email_id, item, occurrence=0):
    return action_key(email_id, item, occurrence).replace('action_reminder_', 'action_calendar_', 1)


def calendar_draft(email, item):
    draft = action_draft(email, item)
    draft.update(end_date=draft['date'], end_time=None, event=None, submitted=None)
    if item.end_time and item.end_time_text:
        draft['end_time'] = datetime.strptime(item.end_time, '%H:%M').time()
    elif item.duration_minutes and item.duration_text and draft['date'] and draft['time']:
        end = datetime.combine(draft['date'], draft['time']) + timedelta(minutes=item.duration_minutes)
        draft.update(end_date=end.date(), end_time=end.time())
    return draft


def confirm_calendar(draft, identity):
    if draft['event'] is not None:
        return draft['event']
    body = event_body(draft, identity)
    # After an uncertain response, lock the submitted payload until recovered.
    # Edits must never silently change an already-created event on retry.
    if draft['submitted'] is not None and draft['submitted'] != body:
        raise ValueError('A previous attempt may have succeeded. Restore the submitted details or check Google Calendar before continuing.')
    previously_submitted = draft['submitted']
    draft['submitted'] = body
    try:
        draft['event'] = create_event(body)
    except CalendarError as exc:
        if not exc.uncertain and previously_submitted is None:
            draft['submitted'] = None
        raise
    draft['open'] = False
    return draft['event']


def render_action_calendar(email, item, occurrence=0):
    key = calendar_key(email.id, item, occurrence)
    drafts = st.session_state.setdefault('action_calendar_drafts', {})
    draft = drafts.setdefault(key, calendar_draft(email, item))
    if draft['event'] is not None:
        st.success('Event added to Google Calendar')
        if draft['event']['link']:
            st.link_button('Open event in Google Calendar', draft['event']['link'])
        return
    if st.button('Add to Calendar', key=key + '_open'):
        draft['open'] = True
    if not draft['open']:
        return
    with st.container(border=True):
        st.markdown('**Review Calendar Event**')
        st.caption("Times use this computer's local timezone. Convert any email timezone to local time before confirming. Creates an event in your primary calendar; no guests are invited.")
        st.text(f'Source email subject: {email.subject}\nSender: {email.sender}')
        st.text(f'Original date: {item.date_text or "Not specified"}\nOriginal time: {item.time_text or "Not specified"}')
        st.caption('End time/duration from email: ' + (item.end_time_text or item.duration_text or
                   'Not specified. Choose an end time yourself; this is user input, not AI-extracted data.'))
        fields = ('title', 'description', 'date', 'time', 'end_date', 'end_time')
        for field in fields:
            if key + '_' + field not in st.session_state:
                st.session_state[key + '_' + field] = draft[field]
        draft['title'] = st.text_input('Event title', key=key + '_title')
        draft['description'] = st.text_area('Event description', key=key + '_description')
        draft['date'] = st.date_input('Event date', value=None, min_value=date.min, max_value=date.max, key=key + '_date')
        draft['time'] = st.time_input('Start time', value=None, key=key + '_time')
        draft['end_date'] = st.date_input('End date (review/select)', value=None, min_value=date.min, max_value=date.max, key=key + '_end_date')
        draft['end_time'] = st.time_input('End time (review/select)', value=None, key=key + '_end_time')
        if st.button('Confirm & Add to Calendar', key=key + '_confirm', type='primary'):
            try:
                confirm_calendar(draft, key)
            except (ValueError, CalendarError) as exc:
                st.error(str(exc))
            except Exception:
                st.error('Google Calendar is unavailable. Your edits are preserved; please try again.')
            else:
                st.rerun()
        if st.button('Cancel', key=key + '_cancel'):
            draft['open'] = False
            st.rerun()
