"""Connector for textup.fr."""

from __future__ import annotations

from typing import cast

import httpx
from bs4 import BeautifulSoup

from unfiltered_paste_index.connectors.base import BaseConnector


class TextUpConnector(BaseConnector):
    site = "textup.fr"
    domains = ("textup.fr",)

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
