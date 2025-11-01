"""Connector for plaster.tymoon.eu."""

from __future__ import annotations

from typing import cast

import httpx
from bs4 import BeautifulSoup

from unfiltered_paste_index.connectors.base import BaseConnector


class PlasterConnector(BaseConnector):
    site = "plaster.tymoon.eu"
    domains = ("plaster.tymoon.eu",)

    def id_from_url(self, url: str) -> str:
        return url.rstrip("/").rsplit("/", 1)[-1]

    async def extract_content(self, response: httpx.Response) -> str | None:
        soup = BeautifulSoup(response.text, "lxml")
        pre = soup.find("pre")
        if pre:
            text = cast(str, pre.get_text("\n")).strip()
            if text:
                return text
        return await super().extract_content(response)
