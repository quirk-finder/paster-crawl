"""Datetime helpers and parsers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

try:
    from dateutil import parser as dateparser
except ImportError:  # pragma: no cover - optional dependency
    dateparser = None

try:  # Python 3.11
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

JST = ZoneInfo("Asia/Tokyo")
UTC = timezone.utc

RELATIVE_PATTERN = re.compile(
    r"(?P<value>\d+)\s+(?P<unit>second|minute|hour|day|week)s?\s+ago", re.I
)
PASSWORD_PATTERN = re.compile(r"(pass(?:word)?|pw|p/?w|pwd|パスワード|合言葉)", re.I)


@dataclass(frozen=True)
class DateParseResult:
    """Wrapper used by parsers for consistent output."""

    dt: datetime | None
    source: str


def ensure_tz(dt: datetime, tz: ZoneInfo) -> datetime:
    """Ensure the given datetime has timezone info and convert to the requested tz."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz)


def parse_text_is_pub(pub_line: str) -> DateParseResult:
    """Parse the ``Pub:`` line from text.is pages."""

    match = re.search(r"Pub:\s*(?P<stamp>.+)$", pub_line, re.I)
    if not match:
        return DateParseResult(dt=None, source="missing")
    stamp = match.group("stamp").strip()
    try:
        parsed = _parse_datetime(stamp)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unable to parse text.is Pub line: {pub_line}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return DateParseResult(dt=parsed.astimezone(JST), source="text.is")


def parse_snippet_host_created(relative: str, reference: datetime | None = None) -> DateParseResult:
    """Convert relative ``created:`` strings from snippet.host into JST datetimes."""

    reference = reference or datetime.now(tz=UTC)
    match = RELATIVE_PATTERN.search(relative.strip())
    if not match:
        return DateParseResult(dt=None, source="missing")
    value = int(match.group("value"))
    unit = match.group("unit").lower()
    delta = {
        "second": timedelta(seconds=value),
        "minute": timedelta(minutes=value),
        "hour": timedelta(hours=value),
        "day": timedelta(days=value),
        "week": timedelta(weeks=value),
    }[unit]
    created = reference - delta
    return DateParseResult(dt=ensure_tz(created, JST), source="snippet.host")


def parse_controlc_pasted(text: str) -> DateParseResult:
    """Parse ``Pasted:`` metadata from controlc.com."""

    match = re.search(r"Pasted:\s*(?P<stamp>.+)$", text, re.I)
    if not match:
        return DateParseResult(dt=None, source="missing")
    stamp = match.group("stamp").strip()
    parsed = _parse_datetime(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return DateParseResult(dt=parsed.astimezone(JST), source="controlc.com")


def is_today_jst(dt: datetime | None, now: datetime | None = None) -> bool:
    """Return True if ``dt`` falls within the JST calendar day of ``now``."""

    if dt is None:
        return False
    now = now or datetime.now(tz=JST)
    dt_jst = dt.astimezone(JST)
    return dt_jst.date() == now.date()


def now_jst() -> datetime:
    """Return current JST datetime."""

    return datetime.now(tz=JST)


def has_password_word(text: str) -> bool:
    """Check whether ``text`` contains a password-like keyword."""

    return bool(PASSWORD_PATTERN.search(text))


URL_PATTERN = re.compile(r"https?://\S+")


def has_url(text: str) -> bool:
    """Return True if the text contains a URL."""

    return bool(URL_PATTERN.search(text))


def _parse_datetime(text: str) -> datetime:
    if dateparser is not None:
        return dateparser.parse(text)
    formats = [
        "%Y %b %d %H:%M %Z",
        "%b %d, %Y %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None and "UTC" in text.upper():
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    raise ValueError(f"Unable to parse datetime: {text}")
