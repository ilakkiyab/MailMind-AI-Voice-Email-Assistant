"""Per-message reply state and explicit review/send controls."""

from email.utils import getaddresses

import streamlit as st

from email_assistant.ai import TONES
from email_assistant.ai.replies import ReplyGenerationError, generate_email_reply, reply_warning
from email_assistant.email import EmailDeliveryError, prepare_email, send_email


def _save_edit(message_id, key):
    state = st.session_state.inbox_replies[message_id]
    state["text"] = st.session_state[key]
    state.pop("pending", None)


def render_reply(email):
    state = st.session_state.setdefault("inbox_replies", {}).setdefault(email.id, {"text": ""})
    key = f"reply_text_{email.id}"
    tone = st.selectbox("Reply tone", TONES, key=f"reply_tone_{email.id}")
    if warning := reply_warning(email.sender, email.body):
        st.warning(warning)
    generate = st.button("Generate AI Reply", key=f"reply_generate_{email.id}")
    regenerate = st.button("Regenerate Reply", key=f"reply_regenerate_{email.id}")
    clear = st.button("Clear Reply", key=f"reply_clear_{email.id}")
    if clear:
        state.clear()
        state["text"] = ""
        st.session_state[key] = ""
    if generate or regenerate:
        state.pop("pending", None)
        try:
            with st.spinner("Generating reply…"):
                result = generate_email_reply(email.sender, email.subject, email.body, tone)
            state.update(text=result.text, truncated=result.truncated)
            st.session_state[key] = result.text
        except ReplyGenerationError as exc:
            st.error(str(exc))
        except Exception:
            st.error("Could not generate this reply. Please try again.")
    if state["text"]:
        if key not in st.session_state:
            st.session_state[key] = state["text"]
        st.text_area("Reply (editable)", key=key, height=200, on_change=_save_edit, args=(email.id, key))
        st.caption("Review and edit the AI reply before sending. Verify all facts and any commitments.")
        if state.get("truncated"):
            st.caption("Long email: only the first 16,000 readable characters were used. Read the full email before replying.")
        st.caption("Sends through your connected Gmail account. Original Gmail thread placement is not guaranteed.")
        if st.button("Send Reply", key=f"reply_send_{email.id}"):
            state.pop("pending", None)
            try:
                addresses = getaddresses([email.sender])
                if len(addresses) != 1 or any(ord(c) < 32 for c in email.sender):
                    raise EmailDeliveryError("The original sender must contain one valid email address.")
                subject = email.subject.strip()
                if not subject.lower().startswith("re:"):
                    subject = "Re: " + subject
                state["pending"] = prepare_email(addresses[0][1], subject, state["text"])
            except (EmailDeliveryError, ValueError) as exc:
                st.error(str(exc))
    if pending := state.get("pending"):
        st.info("Review this exact reply, then confirm delivery.")
        st.text(f"To: {pending.recipient}\nSubject: {pending.subject}\n\n{pending.body}")
        if st.button("Cancel reply send", key=f"reply_cancel_{email.id}"):
            state.pop("pending", None)
            st.rerun()
        if st.button("Confirm and send reply", key=f"reply_confirm_{email.id}", type="primary"):
            state.pop("pending", None)
            try:
                with st.spinner("Sending reply…"):
                    send_email(pending.recipient, pending.subject, pending.body)
                st.success("Reply sent successfully.")
            except EmailDeliveryError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Delivery could not be confirmed. Check Gmail Sent before trying again.")
