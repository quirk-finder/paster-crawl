"""OpenSearch integration."""

from __future__ import annotations

import json
from collections.abc import Iterable

import httpx
import structlog

from .models import PasteRecord

logger = structlog.get_logger(__name__)

MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "edge_ngram_analyzer": {
                    "tokenizer": "edge_ngram_tokenizer",
                    "filter": ["lowercase"],
                }
            },
            "tokenizer": {
                "edge_ngram_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20,
                    "token_chars": ["letter", "digit"],
                }
            },
        }
    },
    "mappings": {
        "properties": {
            "site": {"type": "keyword"},
            "id": {"type": "keyword"},
            "url": {"type": "keyword"},
            "created_at": {"type": "date"},
            "first_seen_at": {"type": "date"},
            "title": {
                "type": "text",
                "fields": {
                    "raw": {"type": "keyword"},
                    "edge": {"type": "text", "analyzer": "edge_ngram_analyzer"},
                },
            },
            "author": {"type": "keyword"},
            "content_text": {
                "type": "text",
                "fields": {
                    "kuromoji": {"type": "text", "analyzer": "kuromoji"},
                },
            },
            "sha256": {"type": "keyword"},
            "has_url": {"type": "boolean"},
            "has_password_word": {"type": "boolean"},
        }
    },
}


class OpenSearchClient:
    def __init__(self, base_url: str, index: str, client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.index = index
        self.client = client

    async def ensure_index(self) -> None:
        index_url = f"{self.base_url}/{self.index}"
        response = await self.client.head(index_url)
        if response.status_code == 200:
            return
        create = await self.client.put(index_url, json=MAPPING)
        create.raise_for_status()
        logger.info("opensearch.index_created", index=self.index)

    async def bulk_index(self, records: Iterable[PasteRecord]) -> None:
        actions = []
        for record in records:
            actions.append(json.dumps({"index": {"_index": self.index, "_id": record.sha256}}))
            actions.append(record.model_dump_json())
        if not actions:
            return
        payload = "\n".join(actions) + "\n"
        response = await self.client.post(
            f"{self.base_url}/_bulk",
            content=payload,
            headers={"Content-Type": "application/x-ndjson"},
        )
        response.raise_for_status()
        logger.info("opensearch.bulk_indexed", count=len(actions) // 2)
