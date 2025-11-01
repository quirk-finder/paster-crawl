"""Robots handling tests."""

from pathlib import Path

import pytest

try:
    from unfiltered_paste_index.robots import RobotsCache, meta_allows
except ImportError:  # pragma: no cover - optional dependency missing
    pytest.skip("httpx not installed", allow_module_level=True)


@pytest.mark.asyncio
async def test_robots_allows(tmp_path: Path) -> None:
    import httpx

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        cache = RobotsCache(client)
        allowed = await cache.allowed("https://example.com/public")
        assert allowed.allowed
        blocked = await cache.allowed("https://example.com/private/secret")
        assert not blocked.allowed


def test_meta_allows() -> None:
    assert meta_allows("<html><head><meta name='robots' content='index,follow'></head></html>")
    assert not meta_allows("<html><head><meta name='robots' content='noindex'></head></html>")
