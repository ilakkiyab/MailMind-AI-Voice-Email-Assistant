"""Explicitly reviewed action-to-reminder drafts, isolated from widget cleanup."""

from dataclasses import asdict
from datetime import date, datetime
import hashlib
import json
import sqlite3

import streamlit as st

from email_assistant.reminders.service import create_reminder, local_reminder_time
from .reminders import reminder_store


def action_key(email_id, item, occurrence=0):
    """Content identity survives reordering; occurrence separates identical items."""
    payload = json.dumps([email_id, asdict(item), occurrence], sort_keys=True)
    return 'action_reminder_' + hashlib.sha256(payload.encode()).hexdigest()


def action_draft(email, item):
    # Invalid extracted values remain blank for explicit user correction.
    try:
        day = date.fromisoformat(item.date) if item.date else None
    except (TypeError, ValueError):
        day = None
    try:
        clock = datetime.strptime(item.time, '%H:%M').time() if item.time else None
    except (TypeError, ValueError):
        clock = None
    context = [item.description, f'Email subject: {email.subject}',
               f'Sender: {email.sender}', f'Action type: {item.type}',
               f'Source: {item.evidence}']
    if item.date_text:
        context.append(f'Date as written ({item.date_source}): {item.date_text}')
    if item.time_text:
        context.append(f'Time as written: {item.time_text}')
    return dict(title=item.title, description='\n'.join(context),
                date=day, time=clock, open=False, reminder_id=None)


def confirm_action_reminder(store, draft):
    """Retry validation/storage failures, but never repeat a successful submission."""
    if draft['reminder_id'] is not None:
        return draft['reminder_id']
    if draft['date'] is None:
        raise ValueError('Please choose a reminder date.')
    if draft['time'] is None:
        raise ValueError('Please choose a reminder time.')
    record_id = create_reminder(store, draft['title'], draft['description'],
                                local_reminder_time(draft['date'], draft['time']))
    draft['reminder_id'] = record_id
    draft['open'] = False
    return record_id


def render_action_reminder(email, item, occurrence=0):
    key = action_key(email.id, item, occurrence)
    drafts = st.session_state.setdefault('action_reminder_drafts', {})
    draft = drafts.setdefault(key, action_draft(email, item))
    if draft['reminder_id'] is not None:
        st.success('Reminder created successfully.')
        if st.button('View Reminders', key=key + '_view'):
            st.session_state.current_page = 'Reminders'
            st.rerun()
        return
    if st.button('Create Reminder', key=key + '_open'):
        draft['open'] = True
    if not draft['open']:
        return
    with st.container(border=True):
        st.markdown('**Review reminder**')
        st.caption("Times use this computer's local timezone. Review any timezone in the email before confirming.")
        if item.time_text:
            st.text(f'Time as written: {item.time_text}')
        # Keep a separate durable draft: Streamlit deletes keys of hidden widgets.
        for field in ('title', 'description', 'date', 'time'):
            widget_key = key + '_' + field
            if widget_key not in st.session_state:
                st.session_state[widget_key] = draft[field]
        draft['title'] = st.text_input('Reminder title', key=key + '_title')
        draft['description'] = st.text_area('Description', key=key + '_description')
        draft['date'] = st.date_input('Reminder date', value=None,
                                      min_value=date.min, max_value=date.max,
                                      key=key + '_date')
        draft['time'] = st.time_input('Reminder time', value=None, key=key + '_time')
        if st.button('Confirm Reminder', key=key + '_confirm', type='primary'):
            try:
                confirm_action_reminder(reminder_store(), draft)
            except ValueError as exc:
                st.error(str(exc))
            except (OSError, sqlite3.Error):
                st.error('Reminder storage is unavailable. Your edits are preserved; please try again.')
            else:
                st.rerun()
        if st.button('Cancel', key=key + '_cancel'):
            draft['open'] = False
            st.rerun()
