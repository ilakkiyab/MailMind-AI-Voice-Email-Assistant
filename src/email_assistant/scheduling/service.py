"""Persistent scheduling and at-most-once delivery through the existing sender."""

from datetime import datetime, timezone
import logging
from threading import Event, Thread

from email_assistant.email import prepare_email, send_email


def create_scheduled_email(store, recipient, subject, body, scheduled_at, *, now=None):
    email = prepare_email(recipient, subject, body)
    if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
        raise ValueError("Schedule time must include a timezone.")
    now = now or datetime.now(timezone.utc)
    if scheduled_at <= now:
        raise ValueError("Schedule date and time must be in the future.")
    return store.create(email, scheduled_at.timestamp())


def local_schedule(day, clock):
    """Use the OS timezone rules for the selected date, including DST."""
    wall = datetime.combine(day, clock).replace(tzinfo=None)
    aware = wall.astimezone()
    if datetime.fromtimestamp(aware.timestamp()) != wall:
        raise ValueError("This local time does not exist because of a clock change. Choose another time.")
    return aware


def process_due_emails(store, *, sender=None, now=None):
    sender = sender or send_email
    instant = (now or datetime.now(timezone.utc)).timestamp()
    store.expire_claims(instant)
    for row in store.due(instant):
        if not store.claim(row['id'], instant):
            continue
        try:
            message_id = sender(row['recipient'], row['subject'], row['body'])
            if not message_id:
                raise ValueError("Unconfirmed delivery")
        except Exception:
            # Never persist provider exception text, which can contain credentials.
            store.finish(row['id'], error=(
                "Gmail sending failed or delivery is unconfirmed. Check Gmail Sent, "
                "authorization and network before scheduling again. No automatic retry."
            ))
        else:
            store.finish(row['id'], message_id=message_id)


class SchedulerWorker:
    """One daemon per app process; SQLite claims also protect multiple processes."""
    def __init__(self, store, interval=15):
        self.store = store
        self.interval = interval
        self.stop = Event()
        self.thread = Thread(target=self.run, name="mailmind-scheduler", daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:
                process_due_emails(self.store)
            except Exception:
                logging.getLogger(__name__).error("Scheduled email processing unavailable; details omitted.")
            self.stop.wait(self.interval)
