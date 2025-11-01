"""Connector for rentry.co."""

from __future__ import annotations

from typing import cast

import httpx
from bs4 import BeautifulSoup

from unfiltered_paste_index.connectors.base import BaseConnector


class RentryConnector(BaseConnector):
    site = "rentry.co"
    domains = ("rentry.co",)

    def id_from_url(self, url: str) -> str:
        return url.rstrip("/").rsplit("/", 1)[-1]

    async def extract_content(self, response: httpx.Response) -> str | None:
        paste_id = self.id_from_url(str(response.url))
        raw_url = str(response.url.join(f"{paste_id}/raw"))
        raw_response = await self.fetch_raw(raw_url)
        if raw_response and raw_response.status_code == 200:
            return cast(str, raw_response.text)
        soup = BeautifulSoup(response.text, "lxml")
        textarea = soup.find("textarea", {"id": "markdown"})
        if textarea:
            text = cast(str, textarea.get_text("\n")).strip()
            if text:
                return text
        return await super().extract_content(response)
