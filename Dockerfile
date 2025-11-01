FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY unfiltered_paste_index ./unfiltered_paste_index
COPY examples ./examples
COPY Makefile ./

RUN pip install --upgrade pip && pip install -e .

CMD ["python", "-m", "unfiltered_paste_index.cli", "--help"]
