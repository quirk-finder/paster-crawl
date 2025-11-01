# unfiltered-paste-index

`unfiltered-paste-index` is an async crawler/indexer that normalizes public pastes containing both URLs and password-like keywords. The tool focuses on the following services:

- text.is
- snippet.host
- rentry.co
- controlc.com
- textup.fr
- paste.rs
- plaster.tymoon.eu

> **Compliance notice**: The project is designed to respect each site's `robots.txt` and meta-robots policies. Only use the `--ignore-robots` flag when you are certain you are allowed to crawl the target content.

## Features

- Async crawling via `httpx` + `asyncio` (HTTP/2 enabled)
- Per-site connectors with parsing logic for timestamps and raw text extraction
- Robots.txt caching and meta-robots enforcement
- Filter pastes that contain a URL _and_ a password keyword (including Japanese variants)
- Discovery via seed URLs, optional sitemaps, and Reddit domain search
- Output to JSONL, SQLite, and optional OpenSearch index with multilingual analyzers
- CLI commands for crawling, seeding, and ingesting
- Comprehensive tooling: `ruff`, `black`, `mypy`, `pytest`

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[development]
```

Install optional tooling (OpenSearch, Docker) as needed.

## Usage

Run crawls per site:

```bash
python -m unfiltered_paste_index.cli crawl --site text.is --today --out out/textis.jsonl
python -m unfiltered_paste_index.cli crawl --site snippet.host --today --out out/snippet.jsonl
```

Helpful flags:

- `--seed <url>` or `--seed-file seeds.txt`: extra URLs to inspect
- `--from-sitemap <url>`: experimental sitemap discovery
- `--ignore-robots`: disable robots compliance (logs a warning; off by default)
- `--concurrency`, `--timeout`, `--rate`: tune fetch behavior

Seed arbitrary URLs (from file or stdin):

```bash
python -m unfiltered_paste_index.cli seed --in seeds.txt --out out/seeds.jsonl
cat seeds.txt | python -m unfiltered_paste_index.cli seed --out out/seeds.jsonl
```

Ingest normalized JSONL into storage:

```bash
python -m unfiltered_paste_index.cli ingest --in out/textis.jsonl --sqlite db.sqlite
python -m unfiltered_paste_index.cli ingest --in out/*.jsonl --opensearch http://localhost:9200 --index pastes
```

The seed and crawl commands emit JSONL records with this schema:

```json
{
  "site": "snippet.host",
  "id": "wokjmc",
  "url": "https://snippet.host/wokjmc",
  "created_at": "2025-11-02T03:10:00+09:00",
  "first_seen_at": "2025-11-02T03:12:33Z",
  "title": "optional",
  "author": "optional",
  "content_text": "plain text, utf-8",
  "sha256": "…",
  "has_url": true,
  "has_password_word": true
}
```

## Quickstart

```
make quickstart
```

The quickstart recipe will:

1. Create a placeholder `.env`
2. Run the seed command against `examples/seeds.txt`
3. Write `out/seeds.jsonl`
4. Load the results into `out/quickstart.sqlite`

## Development

Run code quality checks:

```bash
make lint
make test
```

## Legal & Terms of Service

- Always respect the Terms of Service for each paste provider.
- Honor rate limits and robots restrictions unless you explicitly opt-in to `--ignore-robots`.
- Review and comply with privacy and data-retention policies when storing indexed content.

## Docker (optional)

A minimal Dockerfile and `docker-compose.yml` are provided for containerized runs and local OpenSearch testing. Adjust environment variables in `.env` as needed.
