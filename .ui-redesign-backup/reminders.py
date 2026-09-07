"""Smart Reminder forms, records and compact Dashboard notifications."""

from datetime import datetime, timedelta
import sqlite3
import streamlit as st

from email_assistant.reminders.service import (
    create_reminder, local_reminder_time, reminder_section,
)
from email_assistant.storage.reminders import ReminderStore


@st.cache_resource
def reminder_store():
    return ReminderStore()


def _when(row):
    return datetime.fromtimestamp(row['scheduled_at']).astimezone().strftime('%d %b %Y, %I:%M %p %Z (UTC%z)')


@st.fragment(run_every=15)
def render_reminder_notifications():
    try:
        store = reminder_store()
        alerts = store.due_notifications(datetime.now().timestamp())
        if not alerts:
            return
        summary, view, dismiss = st.columns([3, 2, 1])
        with summary:
            count = len(alerts)
            st.caption(f"🔔 {count} reminder{'s' if count != 1 else ''} due")
        with view:
            if st.button('View Reminders', key='view_due_reminders'):
                st.session_state.current_page = 'Reminders'
                st.rerun()
        with dismiss:
            if st.button('Dismiss', key='dismiss_due_reminders'):
                store.dismiss_notifications(row['id'] for row in alerts)
                st.rerun()
    except (OSError, sqlite3.Error):
        st.error('Reminder notifications are unavailable. Check local data folder permissions.')


def render_reminders():
    st.title('Smart Reminders')
    st.caption("Times use this computer's local timezone. Keep MailMind open and the computer awake. Reminders never send email.")
    if notice := st.session_state.pop('reminder_notice', None):
        st.success(notice)
    try:
        store = reminder_store()
        default = datetime.now() + timedelta(minutes=5)
        with st.form('create_reminder'):
            title = st.text_input('Reminder title', key='reminder_title')
            description = st.text_area('Description (optional)', key='reminder_description')
            day = st.date_input('Reminder date', value=default.date(), key='reminder_date')
            clock = st.time_input('Reminder time', value=default.time().replace(second=0, microsecond=0), key='reminder_time')
            submit = st.form_submit_button('Create reminder', type='primary')
        if submit:
            try:
                create_reminder(store, title, description, local_reminder_time(day, clock))
                st.session_state.reminder_notice = 'Reminder created.'
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        render_reminder_records()
    except (OSError, sqlite3.Error):
        st.error('Reminder storage is unavailable. Check local data folder permissions and try again.')


@st.fragment(run_every=15)
def render_reminder_records():
    try:
        store = reminder_store()
        rows = store.list_all()
        now = datetime.now().astimezone()
        for section in ('Upcoming', 'Past/Overdue', 'Completed'):
            st.subheader(section)
            records = [row for row in rows if reminder_section(row, now) == section]
            if not records:
                st.info(f'No {section.lower()} reminders.')
            for row in records:
                with st.container(border=True):
                    st.text(row['title'])
                    st.text(row['description'] or 'No description.')
                    status = 'Overdue' if section == 'Past/Overdue' else row['status']
                    st.caption(f"Scheduled: {_when(row)} | Status: {status}")
                    if st.button('Mark as completed', key=f"complete_reminder_{row['id']}", disabled=row['status'] == 'Completed'):
                        store.complete(row['id'])
                        st.session_state.reminder_notice = 'Reminder completed.'
                        st.rerun()
                    if st.button('Delete reminder', key=f"delete_reminder_{row['id']}"):
                        store.delete(row['id'])
                        st.session_state.reminder_notice = 'Reminder deleted.'
                        st.rerun()
    except (OSError, sqlite3.Error):
        st.error('Could not load or update reminders. Check local data folder permissions and try again.')
