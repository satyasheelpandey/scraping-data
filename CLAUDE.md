# Portfolio Scraping Pipeline

## Project Overview

Pipeline that discovers portfolio companies from investor websites and enriches records with company websites and M&A deal articles. Runs from `Scraping_code/pipeline.py`.

## Architecture

```
pipeline.py -> processor.py -> scraper.py (crawl4ai)
                             -> llm_extractor.py (GPT-4o-mini)
                             -> google_company_search.py (Knowledge Graph + CSE)
                             -> deal_article_finder.py (Google CSE + URL scoring)
                             -> article_analyzer.py (crawl4ai + GPT-4o-mini deal extraction)
                             -> db.py (PostgreSQL)
```

Each module has a single responsibility. Data flows linearly: crawl -> extract -> enrich -> analyze -> persist.

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
- Internal processing: broad `except Exception` in `processor.py` and `pipeline.py` (intentional -- pipeline must not crash on one URL)
- DB operations: catch `psycopg2.Error` specifically

### Input CSV Format
`input_urls.csv` (project root) with columns: `url, investor_name, investor_link, company_status, strategy, filter_type, js_status_filter, js_strategy_filter, notes`

### Output CSV Format
`output/output_YYYYMMDD_HHMMSS.csv` with 18 columns: `url, investor, investor_link, company, company_url, company_status, strategy, article_1, article_2, article_3, announcement_date, deal_type, deal_value, deal_value_text, currency, deal_stage, strategic_rationale, source_article_url`

Each run creates a new timestamped file — previous outputs are never overwritten. Resume logic scans all `output_*.csv` files and tracks `(url, company_status, strategy)` tuples — same URL with different status/strategy runs independently.

### Output Format (Functions)
- `find_deal_articles()` returns `{"articles": [{"url": str, "score": int}, ...]}`
- `find_official_company_website()` returns `str` (URL or empty string)
- `extract_company_seeds()` returns `List[CompanySeed]`
- `analyze_deal()` returns `DealInfo` (Pydantic model with deal extraction fields)
- `fetch_article_content()` returns `str` (article text via crawl4ai headless browser)

### Deal Type Constraints
Valid `deal_type` values (enforced in `article_analyzer.py`):
`Entry-deal, Merger, Add-on, Carve-out, P2P, MBI, MBO, Funding, Debt, Joint-Venture, Follow-on`

- "Acquisition" is NOT a valid type — automatically mapped to "Entry-deal"
- Normalization via `_DEAL_TYPE_LOOKUP` ensures case-insensitive matching
- LLM prompt instructs GPT-4o-mini to use these exact values

### Database
- Server: `34.91.220.83` / database: `dealsource_raw`
- Schema: `source_db`, Table: `investor_portfolio`
- 40 columns total: 18 pipeline data + 20 financial fields + `is_processed` + `created_at`
- Financial columns (valuation_m, ebitda_m, revenue_multiple, etc.) are populated externally, not by the pipeline
- `is_processed` defaults to `FALSE` — used by downstream consumers
- DB insert is ENABLED in `processor.py` (was previously commented out)

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
- `Scraping_code/utils/investor.py` -- investor data now comes from input CSV
- `Scraping_code/input_urls.csv` -- stale copy; canonical input is `input_urls.csv` in project root

### Print vs Logging
Active modules still use `print()` in several places (27 instances across pipeline.py, processor.py, scraper.py). The `print()` calls in pipeline.py/processor.py are intentional CLI progress output. The ones in scraper.py should be `logger.info/warning`.

### Broad Exception Handling
- `processor.py` and `pipeline.py` catch `Exception` broadly -- this is intentional so one bad URL doesn't crash the entire pipeline
- `scraper.py:101` catches `Exception` broadly during crawl -- should be tightened

### DB Insert Bug (Fixed)
- `db.py` had `UnboundLocalError` when DB connection failed — `conn` was referenced in `finally` before assignment. Fixed by initializing `conn = None` before `try`.

### Missing Test Coverage
- No tests for `llm_extractor.py` or `google_company_search.py` — critical modules
- `tqdm` in requirements.txt is unused — can be removed

### Env Var Validation Inconsistency
- `llm_extractor.py`, `deal_article_finder.py` raise `RuntimeError` (strict)
- `google_company_search.py` logs warning and continues (permissive)
- `db.py` silently accepts `None` (optional)
- Should standardize: strict for required APIs, permissive for optional features

### Crawl Failures (from production runs)
Sites that consistently fail with crawl4ai `RuntimeError` (navigation timeout):
- `hadleyfamilycapital.com` — JS tabs don't load in headless browser
- `alantra.com` — heavy JS portfolio page, `networkidle` times out
- `triton-partners.com` — same navigation timeout pattern
- `affirmacapital.com` — page loads but JS content never renders (0 companies both runs)

**Pattern:** Sites using heavy client-side frameworks (React/Vue SPAs) or aggressive bot detection tend to fail. The pipeline handles this gracefully (logs "No companies found by LLM" and continues).

### Batch Run Tips
- To run a subset: create a temp CSV with header + desired rows, point `INPUT_FILE` at it, run, then revert
- Resume logic scans all `output_*.csv` in the output dir, so partial runs are safe
- Typical throughput: ~1-2 minutes per row (depends on portfolio size and Google API calls)
- Large portfolios (Accel-KKR, Equistone ~100+ companies) take 5+ minutes per row

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
- `crawl4ai>=0.8.6` -- JS-rendered web crawling (portfolio pages + article fetching)
- `openai==1.97.1` -- GPT-4o-mini for company extraction + deal analysis
- `tenacity==9.1.2` -- retry with exponential backoff
- `psycopg2-binary==2.9.9` -- PostgreSQL
- `beautifulsoup4==4.13.4` -- HTML parsing (fallback for article extraction)
- `pydantic` -- schema models (CompanySeed, DealInfo)
