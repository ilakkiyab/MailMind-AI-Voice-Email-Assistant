"""Per-message priority controls, using the existing light-theme widgets."""

import streamlit as st

from email_assistant.ai.priority import PriorityClassificationError, classify_email_priority


LABELS = {"HIGH": "High Priority", "MEDIUM": "Medium Priority", "LOW": "Low Priority"}


def render_priority(email):
    priorities = st.session_state.setdefault("inbox_priorities", {})
    if st.button("Check Priority", key=f"priority_{email.id}"):
        try:
            with st.spinner("Checking email priority…"):
                priorities[email.id] = classify_email_priority(
                    email.sender, email.subject, email.body, received_at=email.received_at,
                )
        except PriorityClassificationError as exc:
            st.error(str(exc))
        except Exception:
            st.error("Could not check this email's priority. Please try again.")
    if result := priorities.get(email.id):
        # Text rendering prevents model-generated HTML, links or images from executing.
        with st.container(key=f"priority_badge_{result.priority}_{email.id}"):
            st.text(LABELS[result.priority])
        st.text(f"Reason: {result.reason}")
        if result.truncated:
            st.caption("Long email: priority is based on the first 16,000 characters. Read the full email for remaining details.")
