# Portfolio Scraping Pipeline

Discovers portfolio companies from investor websites and enriches each record with official company websites and M&A deal articles.

## How It Works

```
input_urls.csv          (investor portfolio page URLs)
       |
   pipeline.py          reads CSV, validates URLs (SSRF protection), resumes from last run
       |
   processor.py         orchestrates per-URL processing
       |
  +----+----+----+
  |         |         |
scraper.py  llm_extractor.py  deal_article_finder.py
  |         |                  |
  |  GPT-4o-mini extracts     Google Custom Search
  |  company names/URLs       + URL relevance scoring
  |         |                  |
  +----+----+----+
       |
  google_company_search.py    (fallback website lookup via Knowledge Graph + CSE)
       |
   db.py + output/output.csv  (PostgreSQL + CSV output)
```

### Pipeline Stages

1. **Crawl** (`scraper.py`) -- JS-rendered page via crawl4ai, plus SPA data endpoint probing (Gatsby `page-data.json`). Extracts anchors, text blocks, DOM tables, and embedded JSON from `<script>` tags.

2. **Extract** (`llm_extractor.py`) -- Sends structured payload to GPT-4o-mini: anchor hints, text blocks, DOM chunks, and any structured data records found in embedded JSON. Returns company names and websites.

3. **Enrich Website** (`google_company_search.py`) -- If the LLM-provided website is missing or looks wrong (matches the investor domain, contains fund-related keywords), falls back to Google Knowledge Graph API, then Custom Search API.

4. **Find Deal Articles** (`deal_article_finder.py`) -- Searches Google Custom Search for `{company} {investor}`, filters blocked domains (PitchBook, PR Newswire, etc.), scores URLs by domain quality and M&A keyword signals, returns top 3.

5. **Persist** (`db.py` + CSV) -- Writes each company record to PostgreSQL (optional) and appends to `output/output.csv`.

## Setup

```bash
cd Scraping_code
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp ../.env.example ../.env
```

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | GPT-4o-mini for company extraction |
| `GOOGLE_API_KEY` | Yes | Knowledge Graph + Custom Search for company websites |
| `GOOGLE_CSE_ID` | Yes | Custom Search Engine ID (company websites) |
| `GOOGLE_DEAL_API_KEY` | Yes | Custom Search for deal articles |
| `GOOGLE_DEAL_CX` | Yes | Custom Search Engine ID (deal articles) |
| `DATABASE_URL` | No | PostgreSQL connection string |

## Usage

### Prepare Input

Create `Scraping_code/input_urls.csv` with one portfolio URL per row:

```csv
url
https://example-pe.com/portfolio
https://another-fund.com/companies
```

### Run

```bash
cd Scraping_code
python3 pipeline.py
```

The pipeline:
- Skips already-processed URLs (resume support via `output/output.csv`)
- Validates URLs against SSRF (private IPs, cloud metadata endpoints)
- Prints progress to stdout
- Writes results to `output/output.csv`

### Output Format

| Column | Description |
|--------|-------------|
| `source_url` | Input portfolio page URL |
| `investor_name` | Derived from domain (e.g., `argonautpe.com` -> `Argonautpe`) |
| `investor_website` | Base domain of the portfolio URL |
| `company_name` | Extracted company name |
| `company_website` | Official company website (LLM or Google fallback) |
| `article_1` | Highest-scored deal article URL |
| `article_2` | Second-highest deal article URL |
| `article_3` | Third-highest deal article URL |

## Project Structure

```
Scraping_code/
  pipeline.py              Entry point, URL validation, resume logic
  processor.py             Per-URL orchestration
  scraper.py               JS-rendered crawling (crawl4ai) + HTML parsing
  llm_extractor.py         GPT-4o-mini company extraction
  google_company_search.py Google Knowledge Graph + CSE website lookup
  deal_article_finder.py   Deal article search + URL scoring
  db.py                    PostgreSQL persistence (optional)
  schema.py                Pydantic model (CompanySeed)
  requirements.txt         Pinned dependencies
  utils/
    investor.py            Investor name extraction from URL
    json_repair.py         LLM JSON output repair
  input_urls.csv           Input file (not committed)
  output/
    output.csv             Pipeline output (not committed)
```

## Tests

```bash
cd /path/to/scraping-data
python3 -m pytest tests/ -v
```

## Security

- SSRF protection: DNS resolution + private IP blocking + cloud metadata endpoint blocking
- Parameterized SQL queries (no string concatenation)
- API keys in `.env` (never committed)
- All dependencies pinned to exact versions
- Rate limit handling with exponential backoff (tenacity)
