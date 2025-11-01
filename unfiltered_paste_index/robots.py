"""Robots.txt handling utilities."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog

logger = structlog.get_logger(__name__)

META_ROBOTS_PATTERN = re.compile(
    r"<meta[^>]+name=[\"']robots[\"'][^>]+content=[\"']([^\"']+)[\"']", re.I
)


@dataclass
class RobotsDecision:
    url: str
    allowed: bool
    reason: str


class RobotsCache:
    """Cache robots.txt lookups per host."""

    def __init__(self, client: httpx.AsyncClient, ignore_robots: bool = False) -> None:
        self._client = client
        self._ignore = ignore_robots
        self._cache: dict[str, RobotFileParser] = {}
        self._lock = asyncio.Lock()

    async def _load(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        async with self._lock:
            if base in self._cache:
                return self._cache[base]
            robots_url = f"{base}/robots.txt"
            parser = RobotFileParser()
            try:
                response = await self._client.get(robots_url, timeout=10)
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    parser.parse(["User-agent: *", "Allow: /"])
            except httpx.HTTPError as exc:  # pragma: no cover - network failure
                logger.warning("robots.fetch_failed", url=robots_url, error=str(exc))
                parser.parse(["User-agent: *", "Allow: /"])
            self._cache[base] = parser
            return parser

    async def allowed(self, url: str, user_agent: str = "unfiltered-paste-index") -> RobotsDecision:
        if self._ignore:
            return RobotsDecision(url=url, allowed=True, reason="ignored")
        parser = await self._load(url)
        allowed = parser.can_fetch(user_agent, url)
        reason = "allowed" if allowed else "blocked-by-robots"
        return RobotsDecision(url=url, allowed=allowed, reason=reason)


def meta_allows(html: str) -> bool:
    """Return True if meta robots allows indexing."""

    match = META_ROBOTS_PATTERN.search(html)
    if not match:
        return True
    content = match.group(1)
    tokens = {token.strip().lower() for token in content.split(",")}
    return "noindex" not in tokens and "none" not in tokens


async def ensure_robot_allowed(cache: RobotsCache, url: str) -> RobotsDecision:
    decision = await cache.allowed(url)
    if not decision.allowed:
        logger.info("robots.blocked", url=url, reason=decision.reason)
    return decision
