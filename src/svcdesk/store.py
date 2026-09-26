# ai-generated: 90% - Claude Code drafted from specs/001-svcdesk/spec.md, reviewed by me
"""SQLite persistence: one JSON document per ticket, in creation order (spec section 8)."""
import json
import os
import sqlite3


class Store:
    # Used only from the event-loop thread, and handlers never await between a read and its write,
    # so a read-modify-write is atomic without a lock.
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS tickets ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, doc TEXT NOT NULL)"
        )
        self._db.commit()

    def add(self, ticket: dict) -> None:
        with self._db:
            self._db.execute("INSERT INTO tickets (id, doc) VALUES (?, ?)", (ticket["id"], json.dumps(ticket)))

    def update(self, ticket: dict) -> None:
        with self._db:
            self._db.execute("UPDATE tickets SET doc = ? WHERE id = ?", (json.dumps(ticket), ticket["id"]))

    def get(self, ticket_id: str) -> dict | None:
        row = self._db.execute("SELECT doc FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self) -> list[dict]:
        return [json.loads(doc) for (doc,) in self._db.execute("SELECT doc FROM tickets ORDER BY seq")]
