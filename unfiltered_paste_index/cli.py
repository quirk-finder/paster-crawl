"""Command line entry point."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import click
import httpx
import structlog

from .connectors import CONNECTOR_REGISTRY, BaseConnector, ConnectorConfig
from .discovery import DiscoveryService
from .models import PasteRecord, compute_sha256, utcnow
from .opensearch import OpenSearchClient
from .robots import RobotsCache, meta_allows
from .store import JsonlStore, SqliteStore
from .utils.datetime import has_password_word, has_url

try:  # pragma: no cover - optional uvloop
    import uvloop
except ImportError:  # pragma: no cover
    uvloop = None

logger = structlog.get_logger(__name__)


def configure_logging(verbose: bool) -> None:
    processors = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(
            serializer=lambda obj: json.dumps(obj, ensure_ascii=False)
        ),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(10 if verbose else 20),
    )


async def create_client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        http2=True, timeout=timeout, headers={"User-Agent": "unfiltered-paste-index/0.1"}
    )


@click.group()
@click.option("--concurrency", default=8, show_default=True, type=int)
@click.option("--timeout", default=20.0, show_default=True, type=float)
@click.option("--rate", default=1.0, show_default=True, type=float)
@click.option(
    "--ignore-robots", is_flag=True, default=False, help="Ignore robots.txt (logs warning)."
)
@click.option("--verbose", is_flag=True, default=False)
@click.pass_context
def cli(
    ctx: click.Context,
    concurrency: int,
    timeout: float,
    rate: float,
    ignore_robots: bool,
    verbose: bool,
) -> None:
    """unfiltered-paste-index CLI."""

    configure_logging(verbose)
    if ignore_robots:
        logger.warning("robots.ignored", message="--ignore-robots enabled")
    if uvloop is not None:
        uvloop.install()
    ctx.obj = {
        "concurrency": concurrency,
        "timeout": timeout,
        "rate": rate,
        "ignore_robots": ignore_robots,
        "verbose": verbose,
    }


@cli.command()
@click.option("--site", type=click.Choice(sorted(CONNECTOR_REGISTRY.keys())), required=True)
@click.option("--today", is_flag=True, default=False, help="Filter to items from JST today.")
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
@click.option("--seed", "seed_urls", multiple=True, help="Additional seed URLs.")
@click.option("--seed-file", "seed_files", type=click.Path(path_type=Path), multiple=True)
@click.option("--from-sitemap", "sitemaps", multiple=True, help="Sitemap URLs to fetch.")
@click.pass_context
def crawl(
    ctx: click.Context,
    site: str,
    today: bool,
    out_path: Path,
    seed_urls: Iterable[str],
    seed_files: Iterable[Path],
    sitemaps: Iterable[str],
) -> None:
    """Crawl a specific site."""

    config = cast(dict[str, Any], ctx.obj)
    asyncio.run(
        _crawl(
            config,
            site=site,
            today=today,
            out_path=out_path,
            seed_urls=list(seed_urls) + _read_seed_files(seed_files),
            sitemap_urls=list(sitemaps),
        )
    )


def _read_seed_files(seed_files: Iterable[Path]) -> list[str]:
    urls: list[str] = []
    for path in seed_files:
        if not path.exists():
            continue
        urls.extend([line.strip() for line in path.read_text().splitlines() if line.strip()])
    return urls


async def _crawl(
    config: dict[str, Any],
    site: str,
    today: bool,
    out_path: Path,
    seed_urls: list[str],
    sitemap_urls: list[str],
) -> None:
    timeout = config["timeout"]
    async with await create_client(timeout) as client:
        robots = RobotsCache(client, ignore_robots=config["ignore_robots"])
        discovery = DiscoveryService(client)
        connector_cls = CONNECTOR_REGISTRY[site]
        connector_config = ConnectorConfig(
            timeout=config["timeout"],
            concurrency=config["concurrency"],
            rate=config["rate"],
            ignore_robots=config["ignore_robots"],
        )
        connector: BaseConnector = connector_cls(
            client=client,
            robots_cache=robots,
            discovery=discovery,
            config=connector_config,
            seed_urls=seed_urls,
            sitemap_urls=sitemap_urls,
        )
        if not today:
            urls = await connector.discover_candidates()
            logger.warning(
                "crawl.without_today", message="--today not set; discovery URLs returned"
            )
            logger.info("crawl.discovery_urls", site=site, count=len(urls))
            return
        records = await connector.crawl_today()
        logger.info("crawl.records", site=site, count=len(records))
        JsonlStore(out_path).write_all(records)


@cli.command()
@click.option("--in", "input_path", type=click.Path(path_type=Path), required=False)
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
@click.pass_context
def seed(ctx: click.Context, input_path: Path | None, out_path: Path) -> None:
    """Ingest URLs from stdin or file."""

    urls = []
    if input_path:
        urls.extend([line.strip() for line in input_path.read_text().splitlines() if line.strip()])
    else:
        urls.extend([line.strip() for line in sys.stdin.read().splitlines() if line.strip()])
    config = cast(dict[str, Any], ctx.obj)
    asyncio.run(_seed(config, urls, out_path))


async def _seed(config: dict[str, Any], urls: list[str], out_path: Path) -> None:
    async with await create_client(config["timeout"]) as client:
        robots = RobotsCache(client, ignore_robots=config["ignore_robots"])
        records: list[PasteRecord] = []
        for url in urls:
            decision = await robots.allowed(url)
            if not decision.allowed:
                logger.info("seed.skipped.robots", url=url)
                continue
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("seed.fetch_failed", url=url, error=str(exc))
                continue
            if not meta_allows(response.text):
                logger.info("seed.meta_blocked", url=url)
                continue
            text = _extract_text(response)
            if not text:
                continue
            if not (has_url(text) and has_password_word(text)):
                continue
            parsed = urlparse(str(response.url))
            record = PasteRecord(
                site=parsed.netloc,
                id=(parsed.path.strip("/") or parsed.netloc),
                url=response.url,
                created_at=None,
                first_seen_at=utcnow(),
                title=_extract_title(response),
                author=None,
                content_text=text,
                sha256=compute_sha256(text),
                has_url=True,
                has_password_word=True,
            )
            records.append(record)
        JsonlStore(out_path).write_all(records)


def _extract_text(response: httpx.Response) -> str | None:
    body = cast(str, response.text)
    if response.headers.get("Content-Type", "").startswith("text/plain"):
        return body
    from bs4 import BeautifulSoup
    from readability import Document

    soup = BeautifulSoup(body, "lxml")
    pre = soup.find("pre")
    if pre:
        text = cast(str, pre.get_text("\n")).strip()
        if text:
            return text
    code = soup.find("code")
    if code:
        text = cast(str, code.get_text("\n")).strip()
        if text:
            return text
    document = Document(body)
    summary = document.summary(html_partial=True)
    summary_soup = BeautifulSoup(summary, "lxml")
    text = cast(str, summary_soup.get_text("\n")).strip()
    return text or None


def _extract_title(response: httpx.Response) -> str | None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, "lxml")
    if soup.title:
        return cast(str, soup.title.get_text(strip=True))
    return None


@cli.command()
@click.option("--in", "inputs", multiple=True, type=click.Path(path_type=Path), required=True)
@click.option("--sqlite", "sqlite_path", type=click.Path(path_type=Path))
@click.option("--opensearch", "opensearch_url", type=str)
@click.option("--index", "index_name", type=str, default="pastes")
@click.pass_context
def ingest(
    ctx: click.Context,
    inputs: Iterable[Path],
    sqlite_path: Path | None,
    opensearch_url: str | None,
    index_name: str,
) -> None:
    """Load JSONL into storage."""

    config = cast(dict[str, Any], ctx.obj)
    asyncio.run(_ingest(config, list(inputs), sqlite_path, opensearch_url, index_name))


async def _ingest(
    config: dict[str, Any],
    inputs: list[Path],
    sqlite_path: Path | None,
    opensearch_url: str | None,
    index_name: str,
) -> None:
    records: list[PasteRecord] = []
    for path in inputs:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            records.append(PasteRecord.model_validate_json(line))
    if sqlite_path:
        store = SqliteStore(sqlite_path)
        store.insert_many(records)
        store.close()
    if opensearch_url:
        async with await create_client(config["timeout"]) as client:
            opensearch = OpenSearchClient(opensearch_url, index_name, client)
            await opensearch.ensure_index()
            await opensearch.bulk_index(records)
