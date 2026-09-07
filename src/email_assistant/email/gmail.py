"""Local, single-user Gmail OAuth, sending and inbox reading. No Streamlit dependencies."""

import base64
import binascii
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import webbrowser

from email_validator import EmailNotValidError, validate_email
from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import httplib2
from requests.exceptions import RequestException
from oauthlib.oauth2 import OAuth2Error

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
INBOX_SCOPES = SCOPES + ["https://www.googleapis.com/auth/gmail.readonly"]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class EmailDeliveryError(Exception):
    """A safe, actionable message suitable for display in the UI."""


@dataclass(frozen=True)
class OutgoingEmail:
    recipient: str
    subject: str
    body: str


def prepare_email(recipient: str, subject: str, body: str) -> OutgoingEmail:
    if not all(isinstance(value, str) and value.strip() for value in (recipient, subject, body)):
        raise EmailDeliveryError("Please provide a recipient, subject and email body before sending.")
    if any(ord(c) < 32 or ord(c) == 127 for c in recipient + subject):
        raise EmailDeliveryError("Recipient and subject must not contain line breaks or control characters.")
    try:
        address = validate_email(recipient.strip(), check_deliverability=False, allow_smtputf8=False)
    except EmailNotValidError:
        raise EmailDeliveryError("Enter one valid recipient email address, such as name@example.com.") from None
    return OutgoingEmail(address.normalized, subject.strip(), body)


def _save_token(path: Path, credentials: Credentials) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".oauth-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(credentials.to_json())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def get_credentials(required_scopes=None, *, preserve_existing_scopes=False) -> Credentials:
    required_scopes = required_scopes or SCOPES
    client_path = PROJECT_ROOT / "credentials.json"
    token_path = PROJECT_ROOT / "token.json"
    if client_path.resolve() == token_path.resolve():
        raise EmailDeliveryError("Google client credentials and token must use different file paths.")
    try:
        credentials = None
        if token_path.exists():
            try:
                credentials = Credentials.from_authorized_user_file(str(token_path))
                if preserve_existing_scopes:
                    required_scopes = sorted(set(required_scopes) | set(credentials.scopes or []))
                if not set(required_scopes).issubset(set(credentials.scopes or [])):
                    credentials = None
            except (ValueError, KeyError, TypeError):
                credentials = None
        if credentials and credentials.valid:
            return credentials
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError:
                credentials = None
        if not credentials or not credentials.valid:
            if not client_path.is_file():
                raise EmailDeliveryError(
                    "Google OAuth credentials are missing. Place your downloaded Desktop app "
                    "OAuth file at credentials.json beside app.py; see README."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_path), required_scopes)
            credentials = flow.run_local_server(
                host="localhost", port=0, open_browser=True, timeout_seconds=120,
                access_type="offline", prompt="consent", authorization_prompt_message="",
                success_message="Gmail authorization complete. You may close this tab.",
            )
        if not credentials or not credentials.valid:
            raise EmailDeliveryError("Gmail authorization was not completed. Please try again.")
        if preserve_existing_scopes:
            granted = credentials.granted_scopes
            if not set(required_scopes).issubset(set(granted if granted is not None else credentials.scopes or [])):
                raise EmailDeliveryError("Google OAuth permission missing. Grant the requested permissions and try again; your existing token is unchanged.")
        _save_token(token_path, credentials)
        return credentials
    except EmailDeliveryError:
        raise
    except (GoogleAuthError, OAuth2Error, ValueError, KeyError, TypeError, AttributeError, Warning, webbrowser.Error):
        raise EmailDeliveryError("Gmail authentication failed or timed out. Check your OAuth configuration and try again.") from None
    except (OSError, RequestException, httplib2.HttpLib2Error):
        raise EmailDeliveryError("Could not connect to Google or read/write OAuth files. Check your network and file permissions.") from None


def send_email(recipient: str, subject: str, body: str, *, thread_id: str | None = None,
               in_reply_to: str | None = None) -> str:
    """Send once; callers must obtain confirmation first. Never retry delivery."""
    draft = prepare_email(recipient, subject, body)
    if thread_id is not None and (not in_reply_to or any(ord(c) < 32 for c in in_reply_to)):
        raise EmailDeliveryError("Original message headers are missing or invalid. Refresh before sending.")
    credentials = get_credentials()
    message = EmailMessage()
    message["To"] = draft.recipient
    message["Subject"] = draft.subject
    if thread_id is not None:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to
    message.set_content(draft.body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    try:
        # Disable credential-refresh replay as well as API retries: delivery is non-idempotent.
        http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=30), max_refresh_attempts=0)
        with build("gmail", "v1", http=http, cache_discovery=False) as service:
            result = service.users().messages().send(userId="me", body={"raw": raw, **({"threadId": thread_id} if thread_id is not None else {})}).execute(num_retries=0)
        if not isinstance(result, dict) or not result.get("id"):
            raise EmailDeliveryError("Gmail did not confirm delivery. Check Gmail Sent before trying again.")
        return result["id"]
    except HttpError as exc:
        status = exc.resp.status
        if status == 400:
            detail = "Gmail rejected the message. Check the recipient and message fields."
        elif status == 401:
            detail = "Gmail authorization expired. Remove the local token file and authorize again."
        elif status == 403:
            detail = "Gmail denied sending. Check Gmail API access, OAuth permission and account limits."
        elif status == 429:
            detail = "Gmail sending limit reached. Wait before trying again."
        else:
            detail = "Gmail could not confirm delivery. Check Gmail Sent before trying again."
        raise EmailDeliveryError(detail) from None
    except (GoogleAuthError, OAuth2Error):
        raise EmailDeliveryError("Gmail authentication failed. Authorize your account again.") from None
    except (OSError, RequestException, httplib2.HttpLib2Error):
        raise EmailDeliveryError("Network error: delivery is uncertain. Check Gmail Sent before trying again.") from None


class InboxError(Exception):
    """Safe inbox failure message; never contains provider exception details."""


class EmailSearchError(Exception):
    """Safe search validation, authentication or provider failure."""


def build_search_query(query: str) -> str:
    """Translate common spoken requests; preserve explicit Gmail search syntax."""
    if not isinstance(query, str) or not query.strip():
        raise EmailSearchError("Please type or transcribe a search query first.")
    query = query.strip()
    match = re.fullmatch(
        r"(?:find|show)(?:\s+me)?\s+(?:emails|messages)\s+(from|about|containing)\s+(.+)",
        query, flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        kind, terms = match.groups()
        terms = terms.strip().rstrip(".?!").strip()
        if not terms:
            raise EmailSearchError("Please include a sender or search words.")
        if kind.lower() == "from":
            # Keep a spoken sender with spaces together as one Gmail operand.
            terms = terms.strip('"').replace('"', "")
            return f'from:"{terms}"'
        return terms
    return query


def search_emails(query: str) -> list["InboxEmail"]:
    """Search the connected inbox, returning up to 20 matches without marking read."""
    gmail_query = build_search_query(query)
    try:
        credentials = get_credentials(INBOX_SCOPES)
        http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=30), max_refresh_attempts=0)
        with build("gmail", "v1", http=http, cache_discovery=False) as service:
            messages = service.users().messages()
            listing = messages.list(
                userId="me", labelIds=["INBOX"], q=gmail_query, maxResults=20,
            ).execute()
            emails = []
            for item in listing.get("messages", [])[:20]:
                try:
                    resource = messages.get(userId="me", id=item["id"], format="raw").execute()
                except HttpError as exc:
                    if exc.resp.status == 404:
                        continue
                    raise
                emails.append(parse_inbox_message(resource))
        return sorted(emails, key=lambda email: email.received_at, reverse=True)
    except EmailDeliveryError as exc:
        raise EmailSearchError(str(exc)) from None
    except HttpError as exc:
        detail = {
            400: "Gmail could not understand this search. Edit your query and try again.",
            401: "Gmail authorization expired or was revoked. Please reconnect your Gmail account.",
            403: "Gmail denied search access. Check Gmail API access and read-only permission.",
            429: "Gmail is receiving too many requests. Please wait before searching again.",
        }.get(exc.resp.status, "Gmail search is temporarily unavailable. Please try again shortly.")
        raise EmailSearchError(detail) from None
    except (GoogleAuthError, OAuth2Error):
        raise EmailSearchError("Gmail authentication failed. Please authorize your account again.") from None
    except (OSError, RequestException, httplib2.HttpLib2Error):
        raise EmailSearchError("Could not connect to Gmail. Check your network and try searching again.") from None
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, binascii.Error):
        raise EmailSearchError("Gmail returned an unreadable search response. Please try again.") from None


@dataclass(frozen=True)
class InboxEmail:
    id: str
    sender: str
    subject: str
    received_at: datetime
    snippet: str
    body: str


class _ReadableHTML(HTMLParser):
    """Extract text without executing HTML or loading remote resources."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.hidden += 1
        if not self.hidden and tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3"):
            self.fragments.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in ("p", "div", "li", "tr", "h1", "h2", "h3"):
            self.fragments.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.fragments.append(data)


def _readable_body(part):
    if part.get_content_disposition() == "attachment" or part.get_filename():
        return ""
    if part.get_content_maintype() == "multipart":
        children = list(part.iter_parts())
        if part.get_content_subtype() == "alternative":
            children.sort(key=lambda child: child.get_content_type() != "text/plain")
            return next((text for child in children if (text := _readable_body(child))), "")
        if part.get_content_subtype() == "related":
            start = part.get_param("start")
            root = next((child for child in children if child.get("Content-ID") == start),
                        children[0] if children else None)
            return _readable_body(root) if root else ""
        return "\n\n".join(text for child in children if (text := _readable_body(child)))
    if part.get_content_type() not in ("text/plain", "text/html"):
        return ""
    data = part.get_payload(decode=True) or b""
    try:
        text = data.decode(part.get_content_charset() or "utf-8", errors="replace")
    except LookupError:
        text = data.decode("utf-8", errors="replace")
    if part.get_content_type() == "text/html":
        parser = _ReadableHTML()
        parser.feed(text)
        text = "\n".join(" ".join(line.split()) for line in "".join(parser.fragments).splitlines())
    return text.strip()


def parse_inbox_message(resource: dict) -> InboxEmail:
    """Decode Gmail RAW MIME, including encoded headers and transfer encodings."""
    raw = resource["raw"]
    message = BytesParser(policy=policy.default).parsebytes(
        base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)
    )
    return InboxEmail(
        id=resource["id"],
        sender=str(message.get("From", "Unknown sender")),
        subject=str(message.get("Subject", "(No subject)")),
        received_at=datetime.fromtimestamp(int(resource["internalDate"]) / 1000, tz=timezone.utc),
        snippet=unescape(resource.get("snippet", "")),
        body=_readable_body(message) or "No readable text body is available for this email.",
    )


def fetch_inbox() -> list[InboxEmail]:
    """Read the latest ten inbox messages without modifying their read status."""
    try:
        logging.getLogger(__name__).warning("INBOX_DIAG fetch started")
        credentials = get_credentials(INBOX_SCOPES)
        http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=30), max_refresh_attempts=0)
        with build("gmail", "v1", http=http, cache_discovery=False) as service:
            messages = service.users().messages()
            listing = messages.list(userId="me", labelIds=["INBOX"], maxResults=10).execute()
            logging.getLogger(__name__).warning(
                "INBOX_DIAG Gmail list returned count=%d", len(listing.get("messages", []))
            )
            emails = []
            for item in listing.get("messages", [])[:10]:
                try:
                    resource = messages.get(userId="me", id=item["id"], format="raw").execute()
                except HttpError as exc:
                    if exc.resp.status == 404:  # Deleted between listing and retrieval.
                        continue
                    raise
                emails.append(parse_inbox_message(resource))
                logging.getLogger(__name__).warning("INBOX_DIAG parsed count=%d", len(emails))
        logging.getLogger(__name__).warning("INBOX_DIAG returning count=%d", len(emails))
        return sorted(emails, key=lambda email: email.received_at, reverse=True)
    except EmailDeliveryError as exc:
        raise InboxError(str(exc)) from None
    except HttpError as exc:
        if exc.resp.status == 401:
            detail = "Gmail authorization expired or was revoked. Remove the local token.json file and select Refresh Inbox to authorize again."
        elif exc.resp.status == 403:
            detail = "Gmail denied inbox access. Check Gmail API access and grant read-only permission. Then select Refresh Inbox."
        elif exc.resp.status == 429:
            detail = "Gmail is receiving too many requests. Please wait and refresh your inbox again."
        else:
            detail = "Gmail could not load your inbox. Please try Refresh Inbox again shortly."
        raise InboxError(detail) from None
    except (GoogleAuthError, OAuth2Error):
        raise InboxError("Gmail authorization expired or was revoked. Please authorize your account again.") from None
    except (OSError, RequestException, httplib2.HttpLib2Error):
        raise InboxError("Could not connect to Gmail. Check your network and select Refresh Inbox to try again.") from None
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, binascii.Error):
        raise InboxError("Gmail returned an unreadable response. Please select Refresh Inbox to try again.") from None
