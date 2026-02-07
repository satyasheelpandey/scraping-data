# Portfolio Scraping Pipeline

## Project Overview

Pipeline that discovers portfolio companies from investor websites and enriches records with company websites and M&A deal articles. Runs from `Scraping_code/pipeline.py`.

## Architecture

```
pipeline.py -> processor.py -> scraper.py (crawl4ai)
                             -> llm_extractor.py (GPT-4o-mini)
                             -> google_company_search.py (Knowledge Graph + CSE)
                             -> deal_article_finder.py (Google CSE + URL scoring)
                             -> db.py (PostgreSQL, optional)
```

Each module has a single responsibility. Data flows linearly: crawl -> extract -> enrich -> persist.

## Code Patterns

### Retry Pattern
All external API calls use `tenacity` with exponential backoff and specific exception types:
```python
@retry(
    retry=retry_if_exception_type((RateLimitError, requests.ConnectionError, requests.Timeout)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(3),
    reraise=True,
)
```

### Environment Variables
- Each module loads its own env vars at module level via `os.getenv()`
- `deal_article_finder.py` and `llm_extractor.py` call `load_dotenv()` independently
- Validation is inconsistent: some raise `RuntimeError`, some log warnings, some silently accept `None`
- Required vars: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`, `GOOGLE_DEAL_API_KEY`, `GOOGLE_DEAL_CX`
- Optional: `DATABASE_URL`

### Error Handling
- External API calls: use tenacity retry with specific exception types
- Internal processing: broad `except Exception` in `processor.py:112` and `pipeline.py:157` (intentional -- pipeline must not crash on one URL)
- DB operations: catch `psycopg2.Error` specifically

### Output Format
- `find_deal_articles()` returns `{"articles": [{"url": str, "score": int}, ...]}`
- `find_official_company_website()` returns `str` (URL or empty string)
- `extract_company_seeds()` returns `List[CompanySeed]`

## Conventions

### File Naming
- Modules: `snake_case.py`
- Utilities: `utils/snake_case.py`
- Tests: `tests/test_<module_name>.py`

### Function Naming
- Public: `find_deal_articles()`, `crawl_portfolio_page()`
- Private: `_search_google()`, `_is_blocked_domain()`, `_extract_from_html()`
- Constants: `UPPER_SNAKE_CASE` (e.g., `HIGH_VALUE_DOMAINS`, `CRAWL_CONFIG`)

### Progress Output
- `pipeline.py` and `processor.py` use `print()` for user-facing progress (intentional CLI output)
- `scraper.py` uses `print()` for debug output (should migrate to `logging`)
- All modules set up `logger = logging.getLogger(__name__)` for structured logging

## Common Mistakes

### Tests Are Stale
- `tests/test_deal_article_finder.py` references `search_google_for_articles` which was renamed to `_search_google`
- Tests expect `company_name`, `investor_name`, `company_website` in the return dict, but the current API returns only `{"articles": [...]}`
- Tests must be updated before they'll pass

### Dead Files
These files are not imported by any active module and should be deleted:
- `Scraping_code/deal_link_finder.py` -- replaced by `deal_article_finder.py`
- `Scraping_code/deep_crawler.py` -- references deleted `schema.PageDoc`
- `Scraping_code/utils/url_normalizer.py` -- only used by `deep_crawler.py`

### Print vs Logging
Active modules still use `print()` in several places (27 instances across pipeline.py, processor.py, scraper.py). The `print()` calls in pipeline.py/processor.py are intentional CLI progress output. The ones in scraper.py should be `logger.info/warning`.

### Broad Exception Handling
- `processor.py:112` and `pipeline.py:157` catch `Exception` broadly -- this is intentional so one bad URL doesn't crash the entire pipeline
- `scraper.py:101` catches `Exception` broadly during crawl -- should be tightened

## Build & Run

```bash
cd Scraping_code
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # fill in API keys
python3 pipeline.py
```

## Tests

```bash
python3 -m pytest tests/ -v
```

Note: Tests are currently broken due to API changes in `deal_article_finder.py` (see Common Mistakes above).

## Key Dependencies
- `crawl4ai==0.7.7` -- JS-rendered web crawling
- `openai==1.97.1` -- GPT-4o-mini for company extraction
- `tenacity==9.1.2` -- retry with exponential backoff
- `psycopg2-binary==2.9.9` -- PostgreSQL (optional)
- `beautifulsoup4==4.13.4` -- HTML parsing
