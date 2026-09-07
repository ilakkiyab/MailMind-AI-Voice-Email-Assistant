"""SQLite reminder repository, independent of email delivery."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

from .scheduled import DEFAULT_DB


class ReminderStore:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                scheduled_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending'
                    CHECK(status IN ('Pending', 'Completed'))
            )""")
            db.execute('CREATE INDEX IF NOT EXISTS reminders_due ON reminders(status, scheduled_at)')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(reminders)')}
            if 'notification_dismissed' not in columns:
                db.execute('ALTER TABLE reminders ADD COLUMN notification_dismissed INTEGER NOT NULL DEFAULT 0')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, title, description, scheduled_at):
        with self.connect() as db:
            return db.execute(
                'INSERT INTO reminders(title,description,scheduled_at) VALUES (?,?,?)',
                (title, description, scheduled_at),
            ).lastrowid

    def list_all(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM reminders ORDER BY scheduled_at,id')]

    def due(self, now):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM reminders WHERE status='Pending' AND scheduled_at<=? ORDER BY scheduled_at,id",
                (now,),
            )]

    def complete(self, record_id):
        with self.connect() as db:
            return db.execute(
                "UPDATE reminders SET status='Completed' WHERE id=? AND status='Pending'", (record_id,),
            ).rowcount == 1

    def due_notifications(self, now):
        return [row for row in self.due(now) if not row['notification_dismissed']]

    def dismiss_notifications(self, record_ids):
        """Acknowledge only the displayed reminders, without completing them."""
        with self.connect() as db:
            db.executemany(
                'UPDATE reminders SET notification_dismissed=1 WHERE id=?',
                ((record_id,) for record_id in record_ids),
            )

    def delete(self, record_id):
        with self.connect() as db:
            return db.execute('DELETE FROM reminders WHERE id=?', (record_id,)).rowcount == 1
