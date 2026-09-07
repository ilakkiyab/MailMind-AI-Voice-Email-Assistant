"""Reminder validation, local time conversion and session notification selection."""

from datetime import date, datetime, time, timezone

from email_assistant.scheduling.service import local_schedule


def local_reminder_time(day, clock):
    if not isinstance(day, date) or isinstance(day, datetime) or not isinstance(clock, time):
        raise ValueError('Please choose a valid reminder date and time.')
    try:
        return local_schedule(day, clock)
    except (OverflowError, OSError):
        raise ValueError('Please choose a valid reminder date and time.') from None


def create_reminder(store, title, description, scheduled_at, *, now=None):
    if not isinstance(title, str) or not title.strip():
        raise ValueError('Please enter a reminder title.')
    if description is None:
        description = ''
    if not isinstance(description, str):
        raise ValueError('Please enter text for the description or leave it empty.')
    if not isinstance(scheduled_at, datetime) or scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
        raise ValueError('Please choose a valid reminder date and time with a timezone.')
    now = now or datetime.now(timezone.utc)
    if scheduled_at.timestamp() <= now.timestamp():
        raise ValueError('Reminder date and time must be in the future.')
    return store.create(title.strip(), description.strip(), scheduled_at.timestamp())


def new_due_reminders(store, notified_ids, *, now=None):
    """Consume due IDs in the caller's session set; never send email or persist alerts."""
    rows = store.due((now or datetime.now(timezone.utc)).timestamp())
    fresh = [row for row in rows if row['id'] not in notified_ids]
    notified_ids.update(row['id'] for row in fresh)
    return fresh


def reminder_section(row, now):
    if row['status'] == 'Completed':
        return 'Completed'
    return 'Past/Overdue' if row['scheduled_at'] <= now.timestamp() else 'Upcoming'
