"""Reddit discovery implementation."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from unfiltered_paste_index.discovery import DiscoveryResult

logger = structlog.get_logger(__name__)


class RedditDiscovery:
    """Query Reddit's public JSON search endpoint."""

    API_URL = "https://www.reddit.com/search.json"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def search_domain(self, domain: str, limit: int = 25) -> list[DiscoveryResult]:
        params = {"q": f"domain:{domain}", "sort": "new", "limit": str(limit)}
        headers = {"User-Agent": "unfiltered-paste-index/0.1"}
        try:
            response = await self.client.get(
                self.API_URL, params=params, headers=headers, timeout=20
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network errors not deterministic
            logger.warning("discovery.reddit.failed", domain=domain, error=str(exc))
            return []
        payload = response.json()
        items: list[DiscoveryResult] = []
        for child in payload.get("data", {}).get("children", []):
            data = child.get("data", {})
            url = data.get("url_overridden_by_dest") or data.get("url")
            if not url:
                continue
            created = data.get("created_utc")
            created_dt: datetime | None = None
            if created:
                created_dt = datetime.fromtimestamp(float(created), tz=timezone.utc)
            items.append(DiscoveryResult(url=url, created_utc=created_dt))
        return items
