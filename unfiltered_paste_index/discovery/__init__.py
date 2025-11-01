"""Discovery helpers for finding paste URLs."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import structlog

from unfiltered_paste_index.discovery.reddit import RedditDiscovery
from unfiltered_paste_index.utils.datetime import JST, ensure_tz

logger = structlog.get_logger(__name__)


@dataclass
class DiscoveryResult:
    url: str
    created_utc: datetime | None


class DiscoveryService:
    """Aggregate discovery strategies."""

    def __init__(self, client: httpx.AsyncClient, enable_reddit: bool = True) -> None:
        self.client = client
        self.reddit = RedditDiscovery(client) if enable_reddit else None

    async def reddit_today(self, domain: str) -> list[DiscoveryResult]:
        if not self.reddit:
            return []
        results = await self.reddit.search_domain(domain, limit=50)
        today = ensure_tz(datetime.now(tz=timezone.utc), JST).date()
        filtered: list[DiscoveryResult] = []
        for item in results:
            created = item.created_utc
            if created is None:
                filtered.append(item)
                continue
            if ensure_tz(created, JST).date() == today:
                filtered.append(item)
        return filtered

    async def gather(self, domains: Iterable[str]) -> list[DiscoveryResult]:
        tasks = [self.reddit_today(domain) for domain in domains]
        if not tasks:
            return []
        results = await asyncio.gather(*tasks)
        merged: list[DiscoveryResult] = []
        for chunk in results:
            merged.extend(chunk)
        return merged
