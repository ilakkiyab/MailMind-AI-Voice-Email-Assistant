"""Email provider integration and workflows."""

from .gmail import EmailDeliveryError, OutgoingEmail, prepare_email, send_email
from .gmail import InboxEmail, InboxError, fetch_inbox

__all__ = ["EmailDeliveryError", "OutgoingEmail", "prepare_email", "send_email",
           "InboxEmail", "InboxError", "fetch_inbox"]
