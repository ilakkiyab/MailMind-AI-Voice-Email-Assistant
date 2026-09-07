"""Isolated per-account/thread/message drafts and two-step confirmed delivery."""
import streamlit as st
from .theme import page_header, followup_badge
from email_assistant.email.followups import fetch_sent_threads, detect_followups, addresses, FollowupError
from email_assistant.email.gmail import prepare_email, send_email, EmailDeliveryError
from email_assistant.ai.followups import generate_followup
from email_assistant.ai import DraftGenerationError


def _edit(identity, key):
    state = st.session_state.followup_drafts[identity]
    state['text'] = st.session_state[key]
    state.pop('pending', None)


def render_followups():
    page_header("Conversations", "Follow-ups", "See which conversations need your attention and prepare a thoughtful reply.")
    threshold = int(st.number_input('Follow-up threshold (days)', min_value=1, value=3, step=1, key='followup_threshold'))
    st.caption('Checks up to 50 sent conversations from the last 90 days. Conservative response-request detection may miss implicit requests. Any recipient reply marks the conversation Replied. Dates are shown in UTC.')
    if st.button('Refresh Follow-ups') or 'followup_snapshot' not in st.session_state:
        st.session_state.pop('followup_snapshot', None)
        for state in st.session_state.get('followup_drafts', {}).values():
            state.pop('pending', None)
        try:
            with st.spinner('Reading sent conversations…'):
                st.session_state.followup_snapshot = fetch_sent_threads()
        except FollowupError as exc:
            st.error(str(exc))
        except Exception:
            st.error('Could not load follow-ups. Please refresh.')
    if 'followup_snapshot' not in st.session_state:
        return
    account, messages = st.session_state.followup_snapshot
    rows = detect_followups(messages, [account], threshold)
    own = {account} | {a for m in messages if m.sent for a in addresses(m.sender)}
    if not rows:
        st.info('No response-requesting sent conversations found in this scan.')
    for row in rows:
        m = row.message
        identity = f'{account}:{m.thread_id}:{m.id}'
        state = st.session_state.setdefault('followup_drafts', {}).setdefault(identity, {'text': ''})
        with st.expander(f'{m.subject} — {row.status}', expanded=True):
            followup_badge(row.status)
            st.text(f'Recipient: {", ".join(m.recipients)}\nSubject: {m.subject}\nSent date: {m.sent_at:%Y-%m-%d %H:%M UTC}\nDays waiting: {row.days_waiting}\nStatus: {row.status}')
            st.caption(f'Thread ID: {m.thread_id} · Message ID: {m.id}')
            if row.status != 'Follow-up Needed':
                state.pop('pending', None)
                continue
            if state.get('sent'):
                st.success('Follow-up sent. Refresh to update the waiting period.')
                continue
            if st.button('Generate Follow-up', key=f'generate_{identity}'):
                state.pop('pending', None)
                try:
                    state['text'] = generate_followup(m)
                    st.session_state[f'text_{identity}'] = state['text']
                except DraftGenerationError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error('Could not generate a follow-up. Please try again.')
            if state['text']:
                key = f'text_{identity}'
                if key not in st.session_state:
                    st.session_state[key] = state['text']
                st.text_area('Follow-up draft (editable)', key=key, on_change=_edit, args=(identity, key))
                st.caption('Review all facts. Sends to the first To recipient using existing Gmail sending; uses the original Gmail thread. Drafts and threshold last for this session.')
                if st.button('Send Follow-up', key=f'send_{identity}'):
                    try:
                        state['pending'] = prepare_email(next(a for a in m.recipients if a not in own), m.subject if m.subject.lower().startswith('re:') else 'Re: ' + m.subject, state['text'])
                    except EmailDeliveryError as exc:
                        st.error(str(exc))
            if pending := state.get('pending'):
                st.text(f'To: {pending.recipient}\nSubject: {pending.subject}\n\n{pending.body}')
                if st.button('Cancel', key=f'cancel_{identity}'):
                    state.pop('pending', None)
                    st.rerun()
                if st.button('Confirm and send follow-up', key=f'confirm_{identity}'):
                    state.pop('pending', None)
                    try:
                        current_account, current_messages = fetch_sent_threads()
                        current = detect_followups(current_messages, [current_account], threshold)
                        if current_account != account or not any(r.message.id == m.id and r.message.thread_id == m.thread_id and r.status == 'Follow-up Needed' for r in current):
                            st.warning('This conversation has changed. Refresh and review it before sending.')
                            return
                        send_email(pending.recipient, pending.subject, pending.body,
                                   thread_id=m.thread_id, in_reply_to=m.rfc_message_id)
                        state['sent'] = True
                        st.rerun()
                    except (EmailDeliveryError, FollowupError) as exc:
                        st.error(str(exc))
                    except Exception:
                        st.error('Delivery is uncertain. Check Gmail Sent before trying again.')
