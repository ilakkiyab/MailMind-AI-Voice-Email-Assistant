"""SQLite scheduled-email repository. Each operation owns its connection."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "mailmind.db"


class ScheduledEmailStore:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS scheduled_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
                scheduled_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending'
                    CHECK(status IN ('Pending','Sending','Sent','Cancelled','Failed')),
                claimed_at REAL, message_id TEXT, error TEXT
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS scheduled_due ON scheduled_emails(status, scheduled_at)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, email, scheduled_at):
        with self.connect() as db:
            return db.execute(
                "INSERT INTO scheduled_emails(recipient,subject,body,scheduled_at) VALUES (?,?,?,?)",
                (email.recipient, email.subject, email.body, scheduled_at),
            ).lastrowid

    def list_all(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM scheduled_emails ORDER BY scheduled_at, id")]

    def due(self, now):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM scheduled_emails WHERE status='Pending' AND scheduled_at<=? ORDER BY scheduled_at,id",
                (now,),
            )]

    def claim(self, record_id, now):
        # Commit the conditional claim BEFORE network I/O, across threads/processes.
        with self.connect() as db:
            return db.execute(
                "UPDATE scheduled_emails SET status='Sending',claimed_at=? WHERE id=? AND status='Pending' AND scheduled_at<=?",
                (now, record_id, now),
            ).rowcount == 1

    def finish(self, record_id, message_id=None, error=None):
        with self.connect() as db:
            db.execute(
                "UPDATE scheduled_emails SET status=?,message_id=?,error=? WHERE id=? AND status='Sending'",
                ('Failed' if error else 'Sent', message_id, error, record_id),
            )

    def expire_claims(self, now):
        # Interrupted or stuck delivery is uncertain; NEVER put it back in Pending.
        with self.connect() as db:
            db.execute(
                "UPDATE scheduled_emails SET status='Failed',error=? WHERE status='Sending' AND claimed_at<?",
                ("Delivery interrupted or unconfirmed. Check Gmail Sent before scheduling again. No automatic retry.", now - 900),
            )

    def cancel(self, record_id):
        with self.connect() as db:
            return db.execute("UPDATE scheduled_emails SET status='Cancelled' WHERE id=? AND status='Pending'",
                              (record_id,)).rowcount == 1

    def delete(self, record_id):
        with self.connect() as db:
            return db.execute("DELETE FROM scheduled_emails WHERE id=? AND status IN ('Cancelled','Sent','Failed')",
                              (record_id,)).rowcount == 1
