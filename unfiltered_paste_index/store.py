"""Storage backends for unfiltered paste index."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

import orjson
import structlog

from unfiltered_paste_index.models import PasteRecord

logger = structlog.get_logger(__name__)


class JsonlStore:
    """Write records to JSONL files."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def write_all(self, records: Iterable[PasteRecord]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(orjson.dumps(record.model_dump(mode="json")).decode("utf-8"))
                handle.write("\n")
        logger.info("store.jsonl.write", path=str(self.path))


class SqliteStore:
    """Persist records to SQLite."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pastes (
                site TEXT NOT NULL,
                id TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TEXT,
                first_seen_at TEXT NOT NULL,
                title TEXT,
                author TEXT,
                content_text TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                has_url INTEGER NOT NULL,
                has_password_word INTEGER NOT NULL,
                PRIMARY KEY (site, url)
            )
            """
        )
        self.conn.commit()

    def insert(self, record: PasteRecord) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO pastes (
                    site, id, url, created_at, first_seen_at, title, author,
                    content_text, sha256, has_url, has_password_word
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.site,
                    record.id,
                    str(record.url),
                    record.created_at.isoformat() if record.created_at else None,
                    record.first_seen_at.isoformat(),
                    record.title,
                    record.author,
                    record.content_text,
                    record.sha256,
                    int(record.has_url),
                    int(record.has_password_word),
                ),
            )

    def insert_many(self, records: Iterable[PasteRecord]) -> None:
        for record in records:
            self.insert(record)

    def close(self) -> None:
        self.conn.close()
