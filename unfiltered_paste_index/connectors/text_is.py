"""Connector for text.is."""

from __future__ import annotations

import re
from datetime import datetime
from typing import cast

import httpx
from bs4 import BeautifulSoup

from unfiltered_paste_index.connectors.base import BaseConnector
from unfiltered_paste_index.utils.datetime import DateParseResult, parse_text_is_pub


class TextIsConnector(BaseConnector):
    site = "text.is"
    domains = ("text.is",)

    def id_from_url(self, url: str) -> str:
        return url.rstrip("/").rsplit("/", 1)[-1]

    async def parse_created_at(self, response: httpx.Response) -> datetime | None:
        soup = BeautifulSoup(response.text, "lxml")
        info = soup.find(string=re.compile(r"Pub:", re.I))
        if not info:
            return None
        parsed: DateParseResult = parse_text_is_pub(info)
        return parsed.dt

    async def extract_content(self, response: httpx.Response) -> str | None:
        soup = BeautifulSoup(response.text, "lxml")
        article = soup.find("article")
        if article:
            text = cast(str, article.get_text("\n")).strip()
            if text:
                return text
        return await super().extract_content(response)
