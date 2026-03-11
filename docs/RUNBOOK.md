# Runbook

## Running the Pipeline

```bash
cd Scraping_code
source venv/bin/activate
python3 pipeline.py
```

The pipeline reads `input_urls.csv`, processes each URL, and appends results to `output/output.csv`. It automatically resumes from where it left off.

## Common Issues

### "OPENAI_API_KEY missing in .env"

The `.env` file is missing or doesn't contain the key. Copy from `.env.example`:

```bash
cp .env.example .env
# Then edit .env with your actual keys
```

### "GOOGLE_DEAL_API_KEY or GOOGLE_DEAL_CX missing in .env"

Both `GOOGLE_DEAL_API_KEY` and `GOOGLE_DEAL_CX` are required for deal article search. These are separate from `GOOGLE_API_KEY`/`GOOGLE_CSE_ID` (used for company website lookup).

### Rate Limiting (429 errors)

All API calls use tenacity with exponential backoff (2s -> 60s, 3 attempts). If you see persistent 429s:

1. Check your Google API quota in the Cloud Console
2. OpenAI rate limits reset per-minute; wait and re-run
3. The pipeline resumes automatically -- just re-run `python3 pipeline.py`

### Crawl Timeouts

`crawl4ai` has a 30-second page timeout. If a site consistently times out:

- Check if the URL is accessible in a browser
- Some sites block headless browsers; these will produce empty results
- The pipeline continues to the next URL on failure

### No Companies Found

If the LLM returns no companies for a URL:

- The page may require authentication or have bot protection
- Check `scraper.py` output: "SPA data found" means structured data was available
- Very image-heavy portfolio pages (logos only, no text) may not extract well

### Database Connection Errors

`DATABASE_URL` is optional. If not set, the pipeline still writes to CSV. If set but failing:

```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1;"
```

The table `portfolio_companies` is auto-created on first insert.

## Reprocessing a URL

Delete the URL's rows from `output/output.csv`, then re-run the pipeline. The resume logic checks `source_url` in the output file to determine what's already processed.

## Deal Article Scoring

Articles are scored on a 0-100 scale:

| Signal | Score Change |
|--------|-------------|
| Baseline | +50 |
| High-value domain (Reuters, Bloomberg, BusinessWire, etc.) | +30 |
| Deal keywords in path (acqui, merger, funding, etc.) | +20 |
| News path segment (/news/, /press/, /article/) | +10 |
| Deep URL path (2+ segments) | +5 |
| Low-value domain (LinkedIn, Wikipedia, social media) | -40 |
| Homepage or index page | -30 |
| Non-article path (/category/, /tag/, /search) | -20 |
| Non-article file extension (.pdf, .jpg, etc.) | -15 |

Blocked domains (PitchBook, PR Newswire, Preqin, Companies House) are excluded entirely.

## Monitoring

The pipeline prints progress to stdout:

```
URLs in input file : 10
Already processed  : 3
URLs to process now: 7

Processing : https://example.com/portfolio
Investor   : Example
Website    : https://example.com
   Google Search for: Company Name
   Saved: Company Name | articles: 2
   Done portfolio: https://example.com/portfolio
```

For production use, redirect output to a log file:

```bash
python3 pipeline.py 2>&1 | tee pipeline.log
```
