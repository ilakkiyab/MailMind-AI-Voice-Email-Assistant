"""Page renderers for the Streamlit dashboard."""

from collections.abc import Callable
import logging

import streamlit as st
from .theme import page_header
from email_assistant.ui.followups import render_followups
from email_assistant.ui.replies import render_reply
from email_assistant.ui.priority import render_priority
from email_assistant.ui.actions import render_actions
from email_assistant.ui.scheduled import render_scheduled
from email_assistant.ui.reminders import render_reminders
from email_assistant.ui.search import render_search

from email_assistant.ai import DraftGenerationError, TONES, generate_email_draft
from email_assistant.ai.summarization import SummaryGenerationError, summarize_email
from email_assistant.email import EmailDeliveryError, prepare_email, send_email
from email_assistant.email import InboxError, fetch_inbox
from email_assistant.voice import (
    EmptyTranscriptionError,
    InvalidAudioError,
    ModelLoadError,
    NoAudioError,
    TranscriptionAPIError,
    transcribe_audio,
)


FEATURES = (
    ("✎", "Compose with Voice", "Capture your thoughts naturally and turn them into a polished draft.", "Compose Email"),
    ("▣", "Read Inbox", "Review messages, summarize email and extract next steps.", "Inbox"),
    ("✦", "AI Email Summary", "Explore the AI tools available in Compose and Inbox.", "AI Assistant"),
    ("◷", "Scheduled Emails", "Prepare messages now and choose the right time to deliver them.", "Scheduled Emails"),
    ("♢", "Smart Reminders", "Keep track of important replies and follow-ups without the clutter.", "Reminders"),
    ("⌕", "Voice Search", "Find messages quickly using natural, spoken questions.", "Voice Email Search"),
)


def _page_header(eyebrow: str, title: str, subtitle: str) -> None:
    page_header(eyebrow, title, subtitle)


def render_dashboard() -> None:
    _page_header("MailMind workspace", "Dashboard", "Your email, priorities and next steps in one place.")
    st.markdown(
        """
        <div class="hero">
            <div class="hero-kicker">AI Voice-Powered Email Assistant</div>
            <h2>Less time on email. More room to focus.</h2>
            <p>Your voice-first email workspace is ready. Start a draft, scan your inbox, or stay ahead of follow-ups—all from one calm dashboard.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-title">Quick actions</div>', unsafe_allow_html=True)
    for start in range(0, len(FEATURES), 3):
        columns = st.columns(3, gap="medium")
        for column, (icon, title, description, target) in zip(columns, FEATURES[start : start + 3]):
            with column:
                st.markdown(
                    f'<div class="feature-card"><div class="feature-icon">{icon}</div><h3>{title}</h3><p>{description}</p></div>',
                    unsafe_allow_html=True,
                )
                if st.button(f"Open {title}  →", key=f"feature_{title}", use_container_width=True):
                    st.session_state.current_page = target
                    st.rerun()


def _clear_compose_form() -> None:
    st.session_state.pop("pending_email", None)
    for key in ("recipient", "subject", "email_body", "voice_transcription"):
        st.session_state[key] = ""
    st.session_state.pop("draft_notice", None)
    st.session_state.pop("draft_error", None)
    st.session_state.pop("voice_recording", None)


def _generate_email() -> None:
    """Generate before the form widgets render so their values update safely."""
    st.session_state.pop("pending_email", None)
    st.session_state.pop("draft_notice", None)
    st.session_state.pop("draft_error", None)
    try:
        draft = generate_email_draft(
            st.session_state.get("voice_transcription", ""),
            st.session_state.get("email_tone", "Professional"),
        )
    except DraftGenerationError as exc:
        st.session_state.draft_error = str(exc)
        return
    st.session_state.subject = draft.subject
    st.session_state.email_body = draft.body
    st.session_state.draft_notice = "Draft generated. Review and edit it before sending."


def render_compose() -> None:
    _page_header("New message", "Compose Email", "Create a thoughtful email by typing or recording your voice.")

    st.markdown(
        '<div class="voice-panel"><strong>01 · Capture your instructions</strong><p>Record a voice note, then transcribe it into editable text.</p></div>',
        unsafe_allow_html=True,
    )
    if hasattr(st, "audio_input"):
        recording = st.audio_input("Record your email instruction", key="voice_recording")
    else:
        recording = st.file_uploader(
            "Upload a recorded email instruction",
            type=["wav", "mp3", "m4a", "mp4", "mpeg", "mpga", "ogg", "webm", "flac"],
            key="voice_recording",
        )

    if st.button("Transcribe audio", type="primary"):
        if recording is None:
            st.warning("Please record an email instruction before transcribing.")
        else:
            try:
                with st.spinner("Transcribing your recording…"):
                    st.session_state.voice_transcription = transcribe_audio(
                        recording.getvalue(),
                        filename=getattr(recording, "name", "voice_instruction.wav"),
                        content_type=getattr(recording, "type", "audio/wav") or "audio/wav",
                    )
                st.success("Transcription complete. You can edit the text below.")
            except NoAudioError:
                st.warning("The recording is empty. Please record your instruction again.")
            except EmptyTranscriptionError:
                st.warning("No speech was detected. Please try another recording and speak clearly.")
            except InvalidAudioError as exc:
                st.warning(str(exc))
            except (ModelLoadError, TranscriptionAPIError) as exc:
                st.error(str(exc))

    st.text_area(
        "Transcription (editable)",
        key="voice_transcription",
        height=140,
        placeholder="Your transcribed email instruction will appear here…",
    )

    st.markdown('<div class="section-title">02 · Draft and review</div>', unsafe_allow_html=True)
    with st.form("compose_form"):
        st.text_input("Recipient", placeholder="name@example.com", key="recipient")
        st.selectbox("Tone", TONES, key="email_tone")
        st.text_input("Subject", placeholder="What is this email about?", key="subject")
        st.text_area("Email body", placeholder="Write your message here…", height=245, key="email_body")

        ai_column, clear_column, send_column = st.columns([2, 1, 1.5])
        with ai_column:
            st.form_submit_button(
                "✦ Generate with AI",
                use_container_width=True,
                on_click=_generate_email,
            )
        with clear_column:
            st.form_submit_button(
                "Clear", use_container_width=True, on_click=_clear_compose_form
            )
        with send_column:
            send = st.form_submit_button("Send Email", type="primary", use_container_width=True)

    if draft_error := st.session_state.pop("draft_error", None):
        st.error(draft_error)
    if draft_notice := st.session_state.pop("draft_notice", None):
        st.success(draft_notice)
    if send:
        st.session_state.pop("pending_email", None)
        try:
            st.session_state.pending_email = prepare_email(
                st.session_state.recipient, st.session_state.subject, st.session_state.email_body
            )
        except EmailDeliveryError as exc:
            st.warning(str(exc))

    if pending := st.session_state.get("pending_email"):
        st.subheader("Confirm email")
        st.info("Review this exact message before sending. To change it, cancel, edit the draft, then select Send Email again.")
        st.text(f"To: {pending.recipient}\nSubject: {pending.subject}")
        st.text(pending.body)
        st.caption("First use opens Google sign-in on this computer. Approve access within two minutes.")
        if st.button("Cancel send"):
            st.session_state.pop("pending_email", None)
            st.rerun()
        if st.button("Confirm and send", type="primary"):
            # Consume confirmation before I/O so reruns cannot replay the send.
            st.session_state.pop("pending_email", None)
            try:
                with st.spinner("Authorizing Gmail and sending…"):
                    send_email(pending.recipient, pending.subject, pending.body)
                st.session_state.send_success = True
            except EmailDeliveryError as exc:
                st.session_state.send_error = str(exc)
            st.rerun()
    if st.session_state.pop("send_success", False):
        st.success("Email sent successfully")
    if error := st.session_state.pop("send_error", None):
        st.error(error)


def _placeholder_page(title: str, icon: str, description: str) -> None:
    _page_header("Coming in a future phase", title, description)
    st.markdown(
        f'<div class="placeholder"><span>{icon}</span><strong>{title} is ready for its integration phase.</strong><br>This screen intentionally contains no mock data or external API calls.</div>',
        unsafe_allow_html=True,
    )


def render_inbox() -> None:
    with st.container(key="inbox_content"):
        _render_inbox_content()


def _render_inbox_content() -> None:
    _page_header("Your messages", "Inbox", "Review your latest 10 Gmail inbox emails.")
    st.caption("First inbox access may open Google sign-in to add read-only permission. Approve within two minutes.")
    refresh = st.button("Refresh Inbox", type="primary")
    if refresh or "inbox_emails" not in st.session_state:
        st.session_state.pop("inbox_summaries", None)
        st.session_state.pop("inbox_error", None)
        st.session_state.inbox_emails = []
        try:
            with st.spinner("Authorizing Gmail and loading inbox…"):
                st.session_state.inbox_emails = fetch_inbox()
                logging.getLogger(__name__).warning(
                    "INBOX_DIAG Streamlit received count=%d", len(st.session_state.inbox_emails)
                )
        except InboxError as exc:
            logging.getLogger(__name__).warning("Inbox refresh failed (InboxError); safe guidance shown in UI.")
            st.session_state.inbox_error = str(exc)
        except Exception as exc:
            # Provider messages/tracebacks may contain tokens or private email content.
            logging.getLogger(__name__).error(
                "Inbox refresh failed (%s); exception details omitted.", type(exc).__name__
            )
            st.session_state.inbox_error = (
                "Could not load your inbox because of an unexpected error. "
                "Please select Refresh Inbox to try again. If it continues, restart the app."
            )
    if error := st.session_state.get("inbox_error"):
        st.error(error)
        return
    if not st.session_state.inbox_emails:
        st.info("Your inbox is empty. New emails will appear when you select Refresh Inbox.")
        return
    for email in st.session_state.inbox_emails:
        with st.container(border=True, key=f"email_card_{email.id}"):
            # Email content is untrusted: render as text, never HTML or Markdown.
            st.text(f"From: {email.sender}\nSubject: {email.subject}")
            st.caption(email.received_at.astimezone().strftime("Received: %d %b %Y, %I:%M %p %Z"))
            st.text(email.snippet)
            with st.expander("Read email"):
                st.text(email.body)
            summaries = st.session_state.setdefault("inbox_summaries", {})
            if st.button("Summarize with AI", key=f"summarize_{email.id}"):
                try:
                    with st.spinner("Summarizing email…"):
                        summaries[email.id] = summarize_email(email.body)
                except SummaryGenerationError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("Could not summarize this email. Please try again.")
            if summary := summaries.get(email.id):
                st.caption("AI summary")
                # Model output is untrusted too: do not render links or remote images.
                st.text(summary.text)
                if summary.truncated:
                    st.caption("Long email: only the first 16,000 characters were summarized. Read the full email for remaining details.")
            st.caption("AI writing assistance")
            render_reply(email)
            st.divider()
            st.caption("Priority & next steps")
            render_priority(email)
            render_actions(email)
    logging.getLogger(__name__).warning(
        "INBOX_DIAG render completed count=%d", len(st.session_state.inbox_emails)
    )
    st.caption(f"Inbox diagnostics: received and rendered {len(st.session_state.inbox_emails)} messages.")


def render_ai_assistant() -> None:
    _page_header("AI tools", "AI Assistant", "Find the right assistance for your next email task.")
    st.info("AI tools are available inside Compose Email and Inbox. A standalone assistant is not available yet.")
    for title, description, target in (
        ("Draft with AI", "Turn typed or transcribed instructions into an editable email draft.", "Compose Email"),
        ("Understand your inbox", "Summarize messages, draft replies, check priority and extract actions.", "Inbox"),
    ):
        with st.container(border=True):
            st.subheader(title)
            st.caption(description)
            if st.button(f"Open {target}", key=f"assistant_open_{target}"):
                st.session_state.current_page = target
                st.rerun()


def render_settings() -> None:
    _placeholder_page("Settings", "⚙", "Account, voice, and integration preferences will be configured here.")


PAGE_RENDERERS: dict[str, Callable[[], None]] = {
    "Dashboard": render_dashboard,
    "Compose Email": render_compose,
    "Inbox": render_inbox,
    "Follow-ups": render_followups,
    "Voice Email Search": render_search,
    "AI Assistant": render_ai_assistant,
    "Scheduled Emails": render_scheduled,
    "Reminders": render_reminders,
    "Settings": render_settings,
}
