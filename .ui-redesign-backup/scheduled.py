"""Scheduled Emails form and persistent delivery history."""

from datetime import datetime, timedelta
import sqlite3
import streamlit as st

from email_assistant.email import EmailDeliveryError
from email_assistant.scheduling.service import create_scheduled_email, local_schedule, SchedulerWorker
from email_assistant.storage.scheduled import ScheduledEmailStore


@st.cache_resource
def scheduled_store():
    return ScheduledEmailStore()


@st.cache_resource
def start_scheduler():
    return SchedulerWorker(scheduled_store())


def render_scheduled():
    st.title("Scheduled Emails")
    st.caption("Times use this computer's local timezone. Keep MailMind running and the computer awake for delivery.")
    st.info("Schedule email authorizes automatic sending through your connected Gmail account. First use may open Google sign-in.")
    if notice := st.session_state.pop('schedule_notice', None):
        st.success(notice)
    try:
        store = scheduled_store()
        default = datetime.now() + timedelta(minutes=5)
        with st.form('schedule_email'):
            recipient = st.text_input('Recipient', key='schedule_recipient')
            subject = st.text_input('Subject', key='schedule_subject')
            body = st.text_area('Email body', key='schedule_body', height=220)
            day = st.date_input('Schedule date', value=default.date())
            clock = st.time_input('Schedule time', value=default.time().replace(second=0, microsecond=0))
            submit = st.form_submit_button('Schedule email', type='primary')
        if submit:
            try:
                when = local_schedule(day, clock)
                create_scheduled_email(store, recipient, subject, body, when)
                st.success(f"Email scheduled for {when:%d %b %Y, %I:%M %p %Z (UTC%z)}.")
            except (EmailDeliveryError, ValueError) as exc:
                st.error(str(exc))
        render_records()
    except (OSError, sqlite3.Error):
        st.error('Scheduled email storage is unavailable. Check local data folder permissions and restart MailMind.')


@st.fragment(run_every=15)
def render_records():
    st.subheader('Scheduled emails and history')
    st.button('Refresh scheduled emails')
    try:
        store = scheduled_store()
        records = store.list_all()
        if not records:
            st.info('No scheduled emails yet.')
        for row in records:
            with st.container(border=True):
                st.text(f"To: {row['recipient']}\nSubject: {row['subject']}")
                when = datetime.fromtimestamp(row['scheduled_at']).astimezone()
                st.caption(f"Scheduled: {when:%d %b %Y, %I:%M %p %Z (UTC%z)} | Status: {row['status']}")
                if row['error']:
                    st.error(row['error'])
                if row['status'] == 'Sending':
                    st.info('Delivery in progress. Interrupted delivery becomes Failed after 15 minutes; it is never automatically retried.')
                if row['status'] == 'Pending':
                    if st.button('Cancel scheduled email', key=f"cancel_schedule_{row['id']}"):
                        if store.cancel(row['id']):
                            st.session_state.schedule_notice = 'Scheduled email cancelled.'
                            st.rerun()
                        st.warning('This email is no longer pending and cannot be cancelled. Refresh its status.')
                elif row['status'] in ('Cancelled', 'Sent', 'Failed'):
                    if st.button('Delete record', key=f"delete_schedule_{row['id']}"):
                        if store.delete(row['id']):
                            st.session_state.schedule_notice = 'Scheduled email record deleted.'
                            st.rerun()
    except (OSError, sqlite3.Error):
        st.error('Could not load or update scheduled emails. Check local data folder permissions.')
