"""Datetime parser tests."""

from datetime import datetime, timezone

from unfiltered_paste_index.utils.datetime import (
    JST,
    parse_controlc_pasted,
    parse_snippet_host_created,
    parse_text_is_pub,
)


def test_parse_text_is_pub() -> None:
    result = parse_text_is_pub("Pub: 2024 Nov 01 13:45 UTC")
    assert result.dt is not None
    assert result.dt.tzinfo == JST
    assert result.dt.hour == 22  # UTC+9


def test_parse_snippet_host_created_minutes() -> None:
    reference = datetime(2024, 11, 1, 12, 0, tzinfo=timezone.utc)
    result = parse_snippet_host_created("created: 30 minutes ago", reference=reference)
    assert result.dt is not None
    assert result.dt.tzinfo == JST
    assert result.dt.hour == 20


def test_parse_controlc_pasted() -> None:
    result = parse_controlc_pasted("Pasted: Nov 01, 2024 1:00 PM")
    assert result.dt is not None
    assert result.dt.tzinfo == JST
