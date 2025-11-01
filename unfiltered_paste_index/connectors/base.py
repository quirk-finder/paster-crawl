"""Common connector infrastructure."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import cast

import httpx
import structlog
from bs4 import BeautifulSoup
from defusedxml import ElementTree as DefusedET
from readability import Document
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from unfiltered_paste_index.discovery import DiscoveryService
from unfiltered_paste_index.models import PasteRecord, compute_sha256, utcnow
from unfiltered_paste_index.robots import RobotsCache, ensure_robot_allowed, meta_allows
from unfiltered_paste_index.utils.datetime import has_password_word, has_url, is_today_jst

logger = structlog.get_logger(__name__)


@dataclass
class ConnectorConfig:
    timeout: float
    concurrency: int
    rate: float
    ignore_robots: bool


class BaseConnector(ABC):
    """Base class for connectors."""

    site: str
    domains: Sequence[str]

    def __init__(
        self,
        client: httpx.AsyncClient,
        robots_cache: RobotsCache,
        discovery: DiscoveryService,
        config: ConnectorConfig,
        seed_urls: Sequence[str] | None = None,
        sitemap_urls: Sequence[str] | None = None,
    ) -> None:
        self.client = client
        self.robots = robots_cache
        self.discovery = discovery
        self.config = config
        self.log = logger.bind(site=self.site)
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._rate_lock = asyncio.Lock()
        self._last_request: float | None = None
        self._seed_urls = list(seed_urls or [])
        self._sitemap_urls = list(sitemap_urls or [])

    async def rate_limit(self) -> None:
        async with self._rate_lock:
            if self._last_request is None:
                self._last_request = asyncio.get_event_loop().time()
                return
            elapsed = asyncio.get_event_loop().time() - self._last_request
            interval = 1.0 / max(self.config.rate, 0.0001)
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
            self._last_request = asyncio.get_event_loop().time()

    @asynccontextmanager
    async def limited(self):
        async with self._semaphore:
            await self.rate_limit()
            yield

    async def crawl_today(self) -> list[PasteRecord]:
        start = asyncio.get_event_loop().time()
        discovered = await self.discover_candidates()
        seen: set[str] = set()
        tasks: list[asyncio.Task[PasteRecord | None]] = []
        for candidate in discovered:
            if candidate in seen:
                continue
            seen.add(candidate)
            tasks.append(asyncio.create_task(self.process_candidate(candidate)))
        records: list[PasteRecord] = []
        for coro in asyncio.as_completed(tasks):
            record = await coro
            if record is None:
                continue
            candidate_dt = record.created_at or record.first_seen_at
            if not is_today_jst(candidate_dt):
                continue
            records.append(record)
        elapsed = asyncio.get_event_loop().time() - start
        self.log.info(
            "crawl.finished", candidates=len(discovered), records=len(records), seconds=elapsed
        )
        return records

    async def discover_candidates(self) -> list[str]:
        results: list[str] = []
        results.extend(self._seed_urls)
        discovery_hits = await self.discovery.gather(self.domains)
        for item in discovery_hits:
            results.append(item.url)
        direct = await self.direct_discovery()
        results.extend(direct)
        return results

    async def direct_discovery(self) -> list[str]:
        """Connectors can override to implement bespoke discovery."""

        urls: list[str] = []
        for sitemap_url in self._sitemap_urls:
            try:
                response = await self.client.get(sitemap_url, timeout=self.config.timeout)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                self.log.warning("crawl.sitemap_failed", url=sitemap_url, error=str(exc))
                continue
            urls.extend(self.extract_urls_from_sitemap(response))
        return urls

    def extract_urls_from_sitemap(self, response: httpx.Response) -> list[str]:
        urls: list[str] = []
        try:
            root = DefusedET.fromstring(response.text)
        except DefusedET.ParseError:
            return urls
        for url in root.findall("{*}url/{*}loc"):
            if url.text:
                urls.append(url.text.strip())
        return urls

    async def process_candidate(self, url: str) -> PasteRecord | None:
        decision = await ensure_robot_allowed(self.robots, url)
        if not decision.allowed:
            return None
        try:
            async with self.limited():
                response = await self._request_with_retries(url)
        except httpx.HTTPError as exc:
            self.log.warning("crawl.fetch_failed", url=url, error=str(exc))
            return None
        if not meta_allows(response.text):
            self.log.info("crawl.meta_blocked", url=url)
            return None
        content = await self.extract_content(response)
        if not content:
            return None
        has_url_flag = has_url(content)
        has_password_flag = has_password_word(content)
        if not (has_url_flag and has_password_flag):
            return None
        created_at = await self.parse_created_at(response)
        record = PasteRecord(
            site=self.site,
            id=self.id_from_url(str(response.url)),
            url=response.url,
            created_at=created_at,
            first_seen_at=utcnow(),
            title=await self.extract_title(response),
            author=await self.extract_author(response),
            content_text=content,
            sha256=compute_sha256(content),
            has_url=has_url_flag,
            has_password_word=has_password_flag,
        )
        return record

    async def _request_with_retries(self, url: str) -> httpx.Response:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=5),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        ):
            with attempt:
                response = await self.client.get(url, timeout=self.config.timeout)
                response.raise_for_status()
                return response
        raise RuntimeError("unreachable")

    async def extract_content(self, response: httpx.Response) -> str | None:
        if response.headers.get("Content-Type", "").startswith("text/plain"):
            return response.text
        soup = BeautifulSoup(response.text, "lxml")
        pre = soup.find("pre")
        if pre:
            return cast(str, pre.get_text("\n"))
        code = soup.find("code")
        if code:
            return cast(str, code.get_text("\n"))
        document = Document(response.text)
        summary = document.summary(html_partial=True)
        summary_soup = BeautifulSoup(summary, "lxml")
        text = cast(str, summary_soup.get_text("\n")).strip()
        return text or None

    async def extract_title(self, response: httpx.Response) -> str | None:
        soup = BeautifulSoup(response.text, "lxml")
        if soup.title:
            return soup.title.get_text(strip=True)
        return None

    async def extract_author(self, response: httpx.Response) -> str | None:
        return None

    async def parse_created_at(self, response: httpx.Response) -> datetime | None:
        return None

    @abstractmethod
    def id_from_url(self, url: str) -> str:
        """Return stable identifier for the paste."""

    async def fetch_raw(self, url: str) -> httpx.Response | None:
        try:
            async with self.limited():
                response = await self._request_with_retries(url)
        except httpx.HTTPError:
            return None
        return response
