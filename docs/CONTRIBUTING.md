# Contributing

## Development Setup

```bash
git clone https://github.com/satyasheelpandey/scraping-data.git
cd scraping-data/Scraping_code

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# For tests
pip install pytest
```

Copy `.env.example` to `.env` and fill in API keys.

## Architecture

The pipeline flows linearly:

```
pipeline.py -> processor.py -> scraper.py + llm_extractor.py + google_company_search.py + deal_article_finder.py -> db.py
```

Each module has a single responsibility:
- `scraper.py` -- crawling and HTML parsing
- `llm_extractor.py` -- LLM interaction and response parsing
- `google_company_search.py` -- company website discovery
- `deal_article_finder.py` -- deal article search and ranking
- `db.py` -- database persistence
- `pipeline.py` -- orchestration, input validation, resume logic

## Running Tests

```bash
cd /path/to/scraping-data
python3 -m pytest tests/ -v
```

## Adding a New SPA Data Endpoint

To support a new static site generator's data format, add the endpoint pattern to `_try_spa_data_endpoints()` in `scraper.py`:

```python
endpoints = [
    f"{base}/page-data/{path}/page-data.json",  # Gatsby
    f"{base}/_next/data/BUILD_ID/{path}.json",   # Next.js (needs build ID)
]
```

## Adding a New Blocked/High-Value Domain

Edit the constants at the top of `deal_article_finder.py`:

- `BLOCKED_DOMAINS` -- domains that are always excluded from results
- `HIGH_VALUE_DOMAINS` -- domains that get a +30 score boost
- `LOW_VALUE_DOMAINS` -- domains that get a -40 score penalty

## Commit Guidelines

Use conventional commits:

```
feat: add support for Next.js data endpoints
fix: handle empty anchor text in scraper
refactor: simplify URL scoring logic
```
