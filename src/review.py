"""Local simulated review dispositions. Never dispatches a technician or closes a real incident."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class ReviewStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.execute('CREATE TABLE IF NOT EXISTS reviews (order_id TEXT PRIMARY KEY, state TEXT NOT NULL, note TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL)')
            con.execute('CREATE TABLE IF NOT EXISTS review_events (order_id TEXT, state TEXT, note TEXT, version INTEGER, updated_at TEXT)')

    def get(self, order_id):
        with sqlite3.connect(self.path) as con:
            con.row_factory = sqlite3.Row
            row = con.execute('SELECT * FROM reviews WHERE order_id=?', (order_id,)).fetchone()
            return dict(row) if row else None

    def save(self, order_id, state, note, expected_version=0):
        if not order_id.startswith('SIM-WO-'):
            raise ValueError('Only simulated orders are supported.')
        if state not in ('Acknowledged', 'Inspection pending', 'Review completed'):
            raise ValueError('Unknown review state.')
        note = note.strip()
        if not note or len(note) > 2000:
            raise ValueError('Add an inspection note of 1–2000 characters.')
        with sqlite3.connect(self.path, timeout=10) as con:
            con.execute('BEGIN IMMEDIATE')
            current = con.execute('SELECT version FROM reviews WHERE order_id=?', (order_id,)).fetchone()
            if (current[0] if current else 0) != expected_version:
                raise ValueError('This review changed in another session. Refresh before saving.')
            values = (order_id, state, note, expected_version+1, datetime.now(timezone.utc).isoformat())
            con.execute('INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?)', values)
            con.execute('INSERT INTO review_events VALUES (?,?,?,?,?)', values)
        return self.get(order_id)
