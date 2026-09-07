"""Inbox rendering and session state for action extraction."""

from datetime import date, datetime

import streamlit as st

from email_assistant.ai.actions import ActionExtractionError, extract_email_actions
from .action_reminders import action_key, render_action_reminder
from .action_calendar import render_action_calendar


def render_actions(email):
    results = st.session_state.setdefault("inbox_actions", {})
    if st.button("Extract Actions", key=f"actions_{email.id}"):
        try:
            with st.spinner("Extracting actions and deadlines…"):
                results[email.id] = extract_email_actions(
                    email.subject, email.body, received_at=email.received_at, email_id=email.id,
                )
        except ActionExtractionError as exc:
            st.error(str(exc))
        except Exception:
            st.error("Could not extract this email's actions. Please try again.")
    result = results.get(email.id)
    if result is None:
        st.caption('To add an event to Google Calendar, select Extract Actions first. Calendar controls appear below each detected action.')
        return
    st.markdown("**Action & Deadline Analysis**")
    if result.truncated:
        st.caption("Long email: analysis uses the first 16,000 body characters and 2,000 subject characters. Read the full email for remaining details.")
    if not result.items:
        st.info("No actions or deadlines detected in this email.")
        st.caption('Add to Calendar appears only when an action is detected. Try an email explicitly asking you to attend a meeting, interview or appointment, or complete a task. General updates may contain no actions.')
    occurrences = {}
    for item in result.items:
        day = date.fromisoformat(item.date).strftime("%d %b %Y") if item.date else "Not specified"
        clock = datetime.strptime(item.time, "%H:%M").strftime("%I:%M %p") if item.time else "Not specified"
        with st.container(border=True):
            # Plain text keeps model-generated markup and links inert.
            st.text(f"Action: {item.title}\nType: {item.type}\nDate: {day}\nTime: {clock}")
            st.text(f"Description: {item.description}")
            if item.date_source == "inferred":
                st.text(f'Date inferred from “{item.date_text}” using email received date ({result.received_at}).')
            elif item.date_source == "explicit":
                st.text(f'Explicit date: {item.date_text}')
            elif item.date_text:
                st.text(f"Unresolved date: {item.date_text}")
            if item.time_text:
                st.text(f"Time as written: {item.time_text}")
            st.text(f"Source: {item.evidence}")
            identity = action_key(email.id, item)
            occurrence = occurrences.get(identity, 0)
            occurrences[identity] = occurrence + 1
            st.caption("Turn this action into a plan")
            reminder_column, calendar_column = st.columns(2)
            with reminder_column:
                render_action_reminder(email, item, occurrence)
            with calendar_column:
                render_action_calendar(email, item, occurrence)
