"""Data models for unfiltered paste index."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator


class PasteRecord(BaseModel):
    """Normalized representation of a paste."""

    site: str
    id: str
    url: HttpUrl
    created_at: datetime | None
    first_seen_at: datetime
    title: str | None = None
    author: str | None = None
    content_text: str
    sha256: str
    has_url: bool
    has_password_word: bool

    model_config = ConfigDict(use_enum_values=True, frozen=True)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class CrawlStats(BaseModel):
    """Statistics emitted after a crawl run."""

    site: str
    crawled_count: int
    matched_count: int
    duration_seconds: float


class RobotsMode(str):
    """How robots rules were handled."""

    HONORED = "honored"
    IGNORED = "ignored"


class CrawlContext(BaseModel):
    """Runtime context passed into connectors."""

    client_timeout: float
    concurrency: int
    rate: float
    ignore_robots: bool = False
    started_at: datetime = datetime.now(tz=timezone.utc)


def compute_sha256(text: str) -> str:
    """Return the sha256 digest of ``text``."""

    digest = hashlib.sha256()
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def utcnow() -> datetime:
    """Return the current UTC datetime with timezone info."""

    return datetime.now(tz=timezone.utc)


def epoch_seconds() -> float:
    """Return current epoch seconds as float."""

    return time.time()
