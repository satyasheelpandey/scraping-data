"""
Enhanced Deal Article Finder

Discovers deal/investment announcement articles using Google Search
with intelligent URL ranking based on domain quality and content signals.

Ranking logic adapted from news_deals_pipeline article_expander.py
"""
import os
import logging
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, quote
from dotenv import load_dotenv
import requests


load_dotenv()

logger = logging.getLogger(__name__)

# ==================================================
# ENVIRONMENT
# ==================================================

GOOGLE_API_KEY = os.getenv("GOOGLE_DEAL_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_DEAL_CX")

if not GOOGLE_API_KEY or not GOOGLE_CX:
    raise RuntimeError("GOOGLE_DEAL_API_KEY or GOOGLE_DEAL_CX missing in .env")

REQUEST_DELAY = 1.0


# ==================================================
# URL SCORING (from article_expander.py)
# ==================================================

# Domains known for M&A press releases and deal news
HIGH_VALUE_DOMAINS = {
    "prnewswire.com", "businesswire.com", "globenewswire.com",
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "cnbc.com", "dealogic.com",
    "pitchbook.com", "preqin.com", "privateequitywire.co.uk",
    "pe-hub.com", "buyoutsinsider.com", "mergr.com",
}

# Domains unlikely to contain deal-specific content
LOW_VALUE_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "youtube.com", "reddit.com",
    "wikipedia.org", "google.com", "bing.com",
}

# Path keywords that signal M&A deal content
DEAL_KEYWORDS = [
    "acqui", "merger", "deal", "takeover", "buyout", "divest",
    "acquisition", "purchase", "transaction", "completes",
    "announces", "agreement", "press-release", "news-release",
    "press_release", "newsrelease",
]


def score_url_for_deal_relevance(url: str) -> int:
    """
    Score a URL by likelihood of containing M&A deal information.

    Higher score = more likely to have deal content.
    Scoring factors: domain reputation, path keywords, path depth.

    Scoring table:
    ┌─────────────────────────┬───────┬──────────────────────────────────────────────┐
    │         Factor          │ Score │                   Examples                   │
    ├─────────────────────────┼───────┼──────────────────────────────────────────────┤
    │ Baseline                │ 50    │ All URLs start here                          │
    ├─────────────────────────┼───────┼──────────────────────────────────────────────┤
    │ High-value domain       │ +30   │ reuters.com, bloomberg.com, businesswire.com │
    ├─────────────────────────┼───────┼──────────────────────────────────────────────┤
    │ Low-value domain        │ -40   │ linkedin.com, wikipedia.org, youtube.com     │
    ├─────────────────────────┼───────┼──────────────────────────────────────────────┤
    │ Deal keyword in path    │ +20   │ /acquisition/, /merger/, /press-release/     │
    ├─────────────────────────┼───────┼──────────────────────────────────────────────┤
    │ News-style path         │ +10   │ /news/, /press/, /article/                   │
    ├─────────────────────────┼───────┼──────────────────────────────────────────────┤
    │ Deep path (2+ segments) │ +5    │ /2024/company-acquires-target                │
    ├─────────────────────────┼───────┼──────────────────────────────────────────────┤
    │ Bare homepage           │ -30   │ /, /index.html                               │
    ├─────────────────────────┼───────┼──────────────────────────────────────────────┤
    │ Non-article path        │ -20   │ /category/, /search, /profile/               │
    ├─────────────────────────┼───────┼──────────────────────────────────────────────┤
    │ Non-article extension   │ -15   │ .pdf, .jpg, .csv                             │
    └─────────────────────────┴───────┴──────────────────────────────────────────────┘

    Args:
        url: The URL to score

    Returns:
        Integer score (higher = better)
    """
    score = 50  # baseline

    try:
        parsed = urlparse(url.strip())
        domain = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.lower()
    except Exception:
        return score

    # Domain scoring
    for hv in HIGH_VALUE_DOMAINS:
        if domain.endswith(hv):
            score += 30
            break

    for lv in LOW_VALUE_DOMAINS:
        if domain.endswith(lv):
            score -= 40
            break

    # Path keyword scoring
    for kw in DEAL_KEYWORDS:
        if kw in path:
            score += 20
            break

    # Penalize bare homepages (just "/" or empty path)
    if path in ("", "/", "/index.html", "/index.htm"):
        score -= 30

    # Penalize non-article paths (category pages, search, profiles)
    if any(seg in path for seg in ["/category/", "/tag/", "/search", "/pub/dir/", "/profile/"]):
        score -= 20

    # Boost paths that look like specific articles (have slugs or IDs)
    segments = [s for s in path.split("/") if s]
    if len(segments) >= 2:
        score += 5  # deeper paths tend to be specific articles

    # Penalize file extensions that aren't articles
    if path.endswith((".pdf", ".jpg", ".png", ".gif", ".txt", ".csv", ".zip")):
        score -= 15

    # Boost news-style paths
    if any(seg in path for seg in ["/news/", "/press/", "/media/", "/article/", "/stories/"]):
        score += 10

    return score


# ==================================================
# GOOGLE SEARCH
# ==================================================

def search_google_for_articles(company_name: str, investor_name: str) -> List[str]:
    """
    Search Google for deal articles about company and investor.

    Args:
        company_name: Name of the company
        investor_name: Name of the investor

    Returns:
        List of URLs (up to 10)
    """
    # Build query
    query_parts = []
    if company_name:
        query_parts.append(company_name)
    if investor_name:
        query_parts.append(investor_name)

    if not query_parts:
        return []

    query = " ".join(query_parts)

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': GOOGLE_API_KEY,
        'cx': GOOGLE_CX,
        'q': query,
        'num': 10  # Request 10 results
    }

    try:
        logger.info(f"🔍 Google Search: {query}")
        resp = requests.get(url, params=params, timeout=20)

        if resp.status_code != 200:
            logger.error(f"Google API error {resp.status_code}: {resp.text}")
            return []

        data = resp.json()
        items = data.get("items", [])

        if not items:
            logger.warning(f"No Google results for: {query}")
            return []

        urls = []
        for item in items:
            link = item.get("link")
            if link:
                urls.append(link)

        logger.info(f"✅ Found {len(urls)} Google results")
        time.sleep(REQUEST_DELAY)
        return urls

    except Exception as e:
        logger.error(f"Google Search error: {e}")
        return []


# ==================================================
# COMPANY WEBSITE DISCOVERY
# ==================================================

def _identify_company_website(urls: List[str], company_name: str) -> Optional[str]:
    """
    Identify the official company website from URL list.

    Looks for URLs where the domain closely matches the company name.

    Args:
        urls: List of URLs from Google search
        company_name: Name of the company

    Returns:
        Company website URL or None
    """
    if not company_name:
        return None

    # Clean company name for matching
    clean_name = re.sub(r'[^\w\s-]', '', company_name.lower())
    clean_name = re.sub(r'\s+', '', clean_name)

    # Remove common suffixes
    for suffix in ['inc', 'corp', 'corporation', 'llc', 'ltd', 'limited', 'group', 'holdings']:
        clean_name = clean_name.replace(suffix, '')

    for url in urls:
        try:
            domain = urlparse(url).netloc.lower().removeprefix("www.")

            # Check if company name is in domain
            if clean_name in domain.replace('.', '').replace('-', ''):
                # Avoid low-value domains even if they match
                is_low_value = any(lv in domain for lv in LOW_VALUE_DOMAINS)
                if not is_low_value:
                    logger.info(f"✅ Identified company website: {url}")
                    return url

        except Exception:
            continue

    return None


# ==================================================
# MAIN API
# ==================================================

def find_deal_articles(company_name: str, investor_name: str) -> Dict:
    """
    Find top 3 deal articles for a company-investor pair.

    Args:
        company_name: Name of the company
        investor_name: Name of the investor/acquirer

    Returns:
        Dictionary with:
        {
            "company_name": str,
            "investor_name": str,
            "company_website": str or None,
            "articles": [
                {"url": str, "score": int},
                {"url": str, "score": int},
                {"url": str, "score": int}
            ]
        }
    """
    result = {
        "company_name": company_name,
        "investor_name": investor_name,
        "company_website": None,
        "articles": []
    }

    # Validate inputs
    if not company_name and not investor_name:
        return result

    # Search Google
    urls = search_google_for_articles(company_name, investor_name)

    if not urls:
        return result

    # Identify company website
    company_website = _identify_company_website(urls, company_name)
    result["company_website"] = company_website

    # Remove company website from article candidates
    article_urls = [u for u in urls if u != company_website]

    # Score all URLs
    scored_urls = []
    seen_urls = set()

    for url in article_urls:
        # Deduplicate
        if url in seen_urls:
            continue
        seen_urls.add(url)

        score = score_url_for_deal_relevance(url)
        scored_urls.append({
            "url": url,
            "score": score
        })

    # Sort by score (descending)
    scored_urls.sort(key=lambda x: x["score"], reverse=True)

    # Return top 3
    result["articles"] = scored_urls[:3]

    logger.info(f"📊 Ranked {len(scored_urls)} articles, returning top 3")
    return result


# ==================================================
# CLI TEST
# ==================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python deal_article_finder.py <company_name> <investor_name>")
        sys.exit(1)

    company = sys.argv[1]
    investor = sys.argv[2]

    result = find_deal_articles(company, investor)

    print(f"\n🏢 Company: {result['company_name']}")
    print(f"💼 Investor: {result['investor_name']}")
    print(f"🌐 Website: {result['company_website']}")
    print(f"\n📰 Top 3 Articles:")
    for i, article in enumerate(result['articles'], 1):
        print(f"{i}. [{article['score']:3d}] {article['url']}")
