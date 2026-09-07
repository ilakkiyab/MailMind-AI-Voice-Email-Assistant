"""Typed and voice email search using existing Gmail and local voice services."""

import streamlit as st

from email_assistant.email.gmail import EmailSearchError, search_emails
from email_assistant.voice import SpeechToTextError, transcribe_audio


def _clear_search() -> None:
    st.session_state.search_query = ""
    for key in ("search_results", "search_error", "search_submitted_query"):
        st.session_state.pop(key, None)
    # A new recorder widget also discards the previous recording.
    st.session_state.search_recording_version = st.session_state.get("search_recording_version", 0) + 1


def render_search() -> None:
    st.title("Voice Email Search")
    st.caption("Type a query or record your voice, then review the text before searching your Gmail inbox.")
    st.caption('Try “Find emails from Google” or “Show emails about placement”. Gmail syntax such as from:google.com also works.')
    version = st.session_state.get("search_recording_version", 0)
    if hasattr(st, "audio_input"):
        recording = st.audio_input("Record a voice search query", key=f"search_recording_{version}")
    else:
        recording = st.file_uploader(
            "Upload a voice search query", type=["wav", "mp3", "m4a", "ogg", "webm", "flac"],
            key=f"search_recording_{version}",
        )
    if st.button("Transcribe search query", key="search_transcribe"):
        if recording is None:
            st.warning("Please record a search query before transcribing.")
        else:
            try:
                with st.spinner("Transcribing your search…"):
                    st.session_state.search_query = transcribe_audio(
                        recording.getvalue(), filename=getattr(recording, "name", "search.wav"),
                        content_type=getattr(recording, "type", "audio/wav") or "audio/wav",
                    )
                st.success("Transcription complete. Edit the query below, then select Search Emails.")
            except SpeechToTextError as exc:
                st.warning(str(exc))
            except Exception:
                st.error("Could not transcribe this recording. Please record again and retry.")

    st.text_area("Search query (editable)", key="search_query", height=100)
    search_column, clear_column = st.columns(2)
    search = search_column.button("Search Emails", type="primary", key="search_submit")
    clear_column.button("Clear Search", on_click=_clear_search, key="search_clear")
    if search:
        for key in ("search_results", "search_error", "search_submitted_query"):
            st.session_state.pop(key, None)
        try:
            with st.spinner("Searching Gmail…"):
                st.session_state.search_results = search_emails(st.session_state.search_query)
            st.session_state.search_submitted_query = st.session_state.search_query
        except EmailSearchError as exc:
            st.session_state.search_error = str(exc)
        except Exception:
            st.session_state.search_error = "Could not search Gmail because of an unexpected error. Please try again."
    if error := st.session_state.get("search_error"):
        st.error(error)
    if "search_results" not in st.session_state:
        return
    st.text(f'Results for: {st.session_state.search_submitted_query}')
    results = st.session_state.search_results
    if not results:
        st.info("No emails matched your search. Try a different sender or keyword.")
        return
    st.caption(f"Showing {len(results)} matching emails (up to 20 per search), newest first. Only inbox emails are searched.")
    for email in results:
        with st.container(border=True):
            st.text(f"From: {email.sender}\nSubject: {email.subject}")
            st.caption(email.received_at.astimezone().strftime("Received: %d %b %Y, %I:%M %p %Z"))
            st.text(email.snippet)
            with st.expander("Read email"):
                st.text(email.body)
