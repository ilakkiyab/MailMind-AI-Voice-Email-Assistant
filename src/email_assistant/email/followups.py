"""Conservative sent-thread detection using the existing Gmail OAuth and MIME reader."""
import base64
import json
import logging
import time
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses

from . import gmail


class FollowupError(Exception):
    """Safe follow-up lookup failure."""


@dataclass(frozen=True)
class SentMessage:
    id: str
    thread_id: str
    sender: str
    recipients: tuple
    subject: str
    sent_at: datetime
    body: str
    sent: bool
    automated: bool = False
    rfc_message_id: str = ""


@dataclass(frozen=True)
class Followup:
    message: SentMessage
    days_waiting: int
    status: str


def addresses(value):
    return tuple(address.lower() for _, address in getaddresses([value]) if address)


def _payload_mime(payload):
    """Adapt Gmail FULL payloads to the existing attachment/HTML-aware MIME reader."""
    mime = EmailMessage(policy=policy.default)
    for header in payload.get('headers', []):
        # Gmail body.data is already transfer-decoded.
        if header['name'].lower() != 'content-transfer-encoding':
            mime[header['name']] = header['value']
    if payload.get('filename') and not mime.get_filename():
        mime.add_header('Content-Disposition', 'attachment', filename=payload['filename'])
    if 'parts' in payload:
        mime.set_payload([_payload_mime(part) for part in payload['parts']])
    else:
        data = payload.get('body', {}).get('data', '')
        mime.set_payload(base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)))
    return mime


def parse_message(resource, thread_id):
    if 'raw' in resource:
        raw = resource['raw']
        mime = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)))
    else:
        mime = _payload_mime(resource['payload'])
    automated = bool(mime.get('List-Unsubscribe') or mime.get('List-Id')) or str(mime.get('Auto-Submitted', 'no')).lower() != 'no' or str(mime.get('Precedence', '')).lower() in ('bulk', 'list', 'junk')
    return SentMessage(resource['id'], thread_id, str(mime.get('From', '')),
                       addresses(str(mime.get('To', ''))), str(mime.get('Subject', '(No subject)')),
                       datetime.fromtimestamp(int(resource['internalDate']) / 1000, tz=timezone.utc),
                       gmail._readable_body(mime), 'SENT' in resource.get('labelIds', []),
                       automated, str(mime.get('Message-ID', '')))


def requires_response(message):
    # Ignore quoted history: an old question must not make a new FYI actionable.
    body = re.split(r'(?im)^\s*(?:On .+wrote:|From:|>+|-----Original Message)', message.body)[0]
    text = message.subject + '\n' + body
    if message.automated or re.search(r'no[._ -]?reply|do[._ -]?not[._ -]?reply|mailer-daemon|notifications?@|newsletter|unsubscribe', ' '.join(message.recipients) + '\n' + text, re.I):
        return False
    if re.search(r'\b(no (?:response|reply|action) (?:is )?(?:needed|required)|for your information|FYI|automated notification|delivery status notification)\b', text, re.I):
        return False
    return bool(re.search(r'\?|\b(?:please (?:reply|respond|confirm|review|send|share|provide|advise|approve|check|let me know)|could you|can you|would you|let me know|looking forward to (?:your|hearing)|awaiting|requesting|following up|follow.up on)\b', text, re.I))


def detect_followups(messages, own_addresses, threshold=3, now=None):
    if not isinstance(threshold, int) or threshold < 1:
        raise ValueError('Choose a threshold of at least one day.')
    now = now or datetime.now(timezone.utc)
    own = {a.lower() for a in own_addresses}
    own.update(a for m in messages if m.sent for a in addresses(m.sender))
    threads = {}
    for m in messages:
        threads.setdefault(m.thread_id, {})[m.id] = m
    results = []
    for group in threads.values():
        sent = [m for m in group.values() if m.sent]
        if not sent:
            continue
        latest = max(sent, key=lambda m: (m.sent_at, m.id))
        recipients = set(latest.recipients) - own
        if not recipients or not requires_response(latest):
            continue
        replied = any(not m.sent and m.sent_at > latest.sent_at and
                      (set(addresses(m.sender)) - own) & recipients and not m.automated
                      for m in group.values())
        elapsed = max(0, (now - latest.sent_at).total_seconds())
        status = 'Replied' if replied else ('Follow-up Needed' if elapsed >= threshold * 86400 else 'Waiting')
        results.append(Followup(latest, int(elapsed // 86400), status))
    return sorted(results, key=lambda r: r.message.sent_at, reverse=True)


_LOGGER = logging.getLogger(__name__)
_RATE_REASONS = {'rateLimitExceeded', 'userRateLimitExceeded'}
_SAFE_REASONS = _RATE_REASONS | {'dailyLimitExceeded', 'quotaExceeded', 'insufficientPermissions', 'authError', 'notFound', 'forbidden', 'backendError'}


def _http_reason(exc):
    try:
        reasons = [e.get('reason') for e in json.loads(exc.content).get('error', {}).get('errors', [])]
        return next((r for r in reasons if r in _SAFE_REASONS), 'unclassified')
    except (ValueError, TypeError, AttributeError):
        return 'unclassified'


def _execute(request, operation):
    """Only retry read operations, and only bounded transient rate-limit failures."""
    for attempt in range(4):
        try:
            return request.execute(num_retries=0)
        except gmail.HttpError as exc:
            reason = _http_reason(exc)
            limited = exc.resp.status == 429 or (exc.resp.status == 403 and reason in _RATE_REASONS)
            if limited and attempt < 3:
                _LOGGER.warning('Follow-ups %s rate limited; retry %d/3', operation, attempt + 1)
                time.sleep(2 ** (attempt + 1))
                continue
            raise


def fetch_sent_threads():
    """Read up to 50 recent sent threads with one FULL request per conversation."""
    operation = 'authentication'
    try:
        credentials = gmail.get_credentials(gmail.INBOX_SCOPES, preserve_existing_scopes=True)
        http = gmail.AuthorizedHttp(credentials, http=gmail.httplib2.Http(timeout=30), max_refresh_attempts=0)
        operation = 'service initialization'
        with gmail.build('gmail', 'v1', http=http, cache_discovery=False) as service:
            users = service.users()
            operation = 'users.getProfile'
            account = _execute(users.getProfile(userId='me'), operation)['emailAddress'].lower()
            operation = 'users.threads.list (Sent)'
            listing = _execute(users.threads().list(userId='me', q='in:sent newer_than:90d', maxResults=50), operation)
            messages = []
            for thread_id in dict.fromkeys(t['id'] for t in listing.get('threads', [])[:50]):
                operation = 'users.threads.get (full)'
                thread = _execute(users.threads().get(userId='me', id=thread_id, format='full'), operation)
                operation = 'conversation MIME parsing'
                for resource in thread.get('messages', []):
                    messages.append(parse_message(resource, thread_id))
        return account, messages
    except gmail.EmailDeliveryError as exc:
        _LOGGER.warning('Follow-ups failed at %s: authentication error', operation)
        raise FollowupError(str(exc)) from None
    except gmail.HttpError as exc:
        reason = _http_reason(exc)
        status = exc.resp.status
        _LOGGER.warning('Follow-ups failed at %s: HTTP %s (%s)', operation, status, reason)
        if status == 429 or reason in _RATE_REASONS | {'dailyLimitExceeded', 'quotaExceeded'}:
            advice = 'Gmail request quota was reached. Wait before refreshing; OAuth credentials do not need resetting.'
        elif reason == 'insufficientPermissions':
            advice = 'Gmail reports insufficient permission for this operation.'
        else:
            advice = 'Refresh later. Check Gmail API availability if this persists.'
        raise FollowupError(f'Could not load conversations at {operation}: HTTP {status} ({reason}). {advice}') from None
    except Exception as exc:
        # Never log exception text, URLs, IDs, credentials, or email content.
        kind = type(exc).__name__
        _LOGGER.warning('Follow-ups failed at %s: %s', operation, kind)
        raise FollowupError(f'Could not load conversations at {operation} ({kind}). Check connectivity or retry; no partial scan was used.') from None
