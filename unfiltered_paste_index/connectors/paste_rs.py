"""Connector for paste.rs."""

from __future__ import annotations

from typing import cast

import httpx

from unfiltered_paste_index.connectors.base import BaseConnector


class PasteRSConnector(BaseConnector):
    site = "paste.rs"
    domains = ("paste.rs",)

    def id_from_url(self, url: str) -> str:
        return url.rstrip("/").rsplit("/", 1)[-1]

    async def extract_content(self, response: httpx.Response) -> str | None:
        if response.headers.get("Content-Type", "").startswith("text/plain"):
            return cast(str, response.text)
        return await super().extract_content(response)
