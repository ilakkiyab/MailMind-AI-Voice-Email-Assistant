"""Confirmed primary-calendar events using the shared local Google OAuth client."""

from datetime import date, datetime, time, timezone
import hashlib
from urllib.parse import urlsplit

from google.auth.exceptions import GoogleAuthError
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import httplib2
from oauthlib.oauth2 import OAuth2Error
from requests.exceptions import RequestException

from email_assistant.email.gmail import get_credentials, EmailDeliveryError
from email_assistant.scheduling.service import local_schedule

CALENDAR_SCOPE = 'https://www.googleapis.com/auth/calendar.events.owned'


class CalendarError(Exception):
    """Safe message, never raw provider details."""

    def __init__(self, message, *, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


def event_body(draft, identity, *, now=None):
    if not isinstance(draft['title'], str) or not draft['title'].strip():
        raise ValueError('Please enter an event title.')
    for field in ('date', 'end_date'):
        if not isinstance(draft[field], date) or isinstance(draft[field], datetime):
            raise ValueError('Please choose an event date and end date.')
    for field in ('time', 'end_time'):
        if not isinstance(draft[field], time):
            raise ValueError('Please choose a start time and end time.')
    try:
        start = local_schedule(draft['date'], draft['time'])
        end = local_schedule(draft['end_date'], draft['end_time'])
    except (OSError, OverflowError):
        raise ValueError('Please choose valid event dates and times.') from None
    if end <= start:
        raise ValueError('End time must be after start time.')
    if end <= (now or datetime.now(timezone.utc)):
        raise ValueError('The event is entirely in the past. Choose a future date/time.')
    return dict(id=hashlib.sha256(('mailmind-calendar-v1:' + identity).encode()).hexdigest(),
                summary=draft['title'].strip(), description=draft['description'],
                start={'dateTime': start.isoformat()}, end={'dateTime': end.isoformat()})


def safe_event_link(value):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme == 'https' and url.hostname in {'calendar.google.com', 'www.google.com'}
                and not url.username and not url.password and url.port in (None, 443)
                and (url.hostname == 'calendar.google.com' or url.path.startswith('/calendar/'))):
            return value
    except ValueError:
        pass
    return None


def create_event(body):
    """Caller confirms first. Stable Google event ID also protects uncertain retries."""
    try:
        credentials = get_credentials([CALENDAR_SCOPE], preserve_existing_scopes=True)
        http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=30), max_refresh_attempts=0)
        with build('calendar', 'v3', http=http, cache_discovery=False) as service:
            events = service.events()
            try:
                result = events.insert(calendarId='primary', body=body, sendUpdates='none').execute(num_retries=0)
            except HttpError as exc:
                if exc.resp.status != 409:
                    raise
                result = events.get(calendarId='primary', eventId=body['id']).execute(num_retries=0)
        if not isinstance(result, dict) or result.get('id') != body['id'] or result.get('status') == 'cancelled':
            raise CalendarError('Google did not confirm an active event. Check Calendar before retrying; the same event ID will be reused.', uncertain=True)
        return {'id': result['id'], 'link': safe_event_link(result.get('htmlLink'))}
    except EmailDeliveryError as exc:
        raise CalendarError(str(exc).replace('Gmail', 'Google Calendar')) from None
    except HttpError as exc:
        if exc.resp.status == 403:
            # Inspect only to classify; never display provider content.
            disabled = any(code in exc.content for code in (b'accessNotConfigured', b'SERVICE_DISABLED', b'serviceDisabled'))
            message = ('Google Calendar API is not enabled. Enable it in the Google Cloud project used by credentials.json.'
                       if disabled else 'Calendar OAuth permission missing or access denied. Re-authorize with Calendar permission and check account policy.')
        else:
            message = {400: 'Google Calendar rejected the event. Review its dates and times.',
                       401: 'Google Calendar token expired or was revoked. Re-authorize your Google account.',
                       429: 'Google Calendar is busy. Wait and retry.'}.get(exc.resp.status,
                       'Google Calendar API failed. Your edits are preserved; retry uses the same event ID.')
        raise CalendarError(message, uncertain=exc.resp.status >= 500 or exc.resp.status in (404, 409)) from None
    except (GoogleAuthError, OAuth2Error):
        raise CalendarError('Google Calendar authentication failed. Check credentials and authorize again.') from None
    except (OSError, RequestException, httplib2.HttpLib2Error):
        raise CalendarError('Could not connect to Google Calendar. Check your network and retry; the same event ID prevents duplicate creation.', uncertain=True) from None
