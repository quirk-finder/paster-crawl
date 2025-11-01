PYTHON ?= python3

.PHONY: install lint test quickstart

install:
$(PYTHON) -m pip install -e .[development]

lint:
ruff check .
black --check .
mypy .

test:
pytest

quickstart:
@test -f .env || echo "# environment variables" > .env
mkdir -p out
$(PYTHON) -m unfiltered_paste_index.cli seed --in examples/seeds.txt --out out/seeds.jsonl
$(PYTHON) -m unfiltered_paste_index.cli ingest --in out/seeds.jsonl --sqlite out/quickstart.sqlite
