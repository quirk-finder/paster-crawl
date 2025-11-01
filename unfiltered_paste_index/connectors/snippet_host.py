"""Connector for snippet.host."""

from __future__ import annotations

import re
from datetime import datetime
from typing import cast

import httpx
from bs4 import BeautifulSoup

from unfiltered_paste_index.connectors.base import BaseConnector
from unfiltered_paste_index.utils.datetime import DateParseResult, parse_snippet_host_created


class SnippetHostConnector(BaseConnector):
    site = "snippet.host"
    domains = ("snippet.host",)

    def id_from_url(self, url: str) -> str:
        return url.rstrip("/").rsplit("/", 1)[-1]

    async def extract_content(self, response: httpx.Response) -> str | None:
        snippet_id = self.id_from_url(str(response.url))
        raw_url = str(response.url.join(f"{snippet_id}/raw"))
        raw_response = await self.fetch_raw(raw_url)
        if raw_response and raw_response.status_code == 200:
            return cast(str, raw_response.text)
        return await super().extract_content(response)

    async def parse_created_at(self, response: httpx.Response) -> datetime | None:
        soup = BeautifulSoup(response.text, "lxml")
        info = soup.find(string=re.compile(r"created:\s*", re.I))
        if not info:
            return None
        parsed: DateParseResult = parse_snippet_host_created(info)
        return parsed.dt
