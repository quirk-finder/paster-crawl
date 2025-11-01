"""Connector for controlc.com."""

from __future__ import annotations

import re
from datetime import datetime
from typing import cast

import httpx
from bs4 import BeautifulSoup

from unfiltered_paste_index.connectors.base import BaseConnector
from unfiltered_paste_index.utils.datetime import DateParseResult, parse_controlc_pasted


class ControlCConnector(BaseConnector):
    site = "controlc.com"
    domains = ("controlc.com",)

    def id_from_url(self, url: str) -> str:
        return url.rstrip("/").rsplit("/", 1)[-1]

    async def extract_content(self, response: httpx.Response) -> str | None:
        soup = BeautifulSoup(response.text, "lxml")
        textarea = soup.find("textarea")
        if textarea:
            text = cast(str, textarea.get_text("\n")).strip()
            if text:
                return text
        return await super().extract_content(response)

    async def parse_created_at(self, response: httpx.Response) -> datetime | None:
        soup = BeautifulSoup(response.text, "lxml")
        info = soup.find(string=re.compile(r"Pasted:\s*", re.I))
        if not info:
            return None
        parsed: DateParseResult = parse_controlc_pasted(info)
        return parsed.dt
