"""
Deal Article Finder

Discovers deal/investment articles via Google Custom Search
and ranks URLs by domain quality and M&A content signals.
"""
import os
import logging
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_DEAL_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_DEAL_CX")

if not GOOGLE_API_KEY or not GOOGLE_CX:
    raise RuntimeError("GOOGLE_DEAL_API_KEY or GOOGLE_DEAL_CX missing in .env")


class RateLimitError(Exception):
    """Raised when API returns HTTP 429."""


# --- domain / path scoring constants ---

BLOCKED_DOMAINS = {
    "pitchbook.com",
    "prnewswire.com",
    "prweb.com",
    "preqin.com",
    "find-and-update.company-information.service.gov.uk",
}

HIGH_VALUE_DOMAINS = {
    "businesswire.com", "globenewswire.com",
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "cnbc.com", "dealogic.com",
    "privateequitywire.co.uk",
    "pe-hub.com", "buyoutsinsider.com", "mergr.com",
    "techcrunch.com", "finsmes.com", "thesaasnews.com",
}

LOW_VALUE_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "youtube.com", "reddit.com",
    "wikipedia.org", "google.com", "bing.com",
}

DEAL_PATH_KEYWORDS = [
    "acqui", "merger", "deal", "takeover", "buyout", "divest",
    "acquisition", "purchase", "transaction", "completes",
    "announces", "agreement", "press-release", "news-release",
    "press_release", "newsrelease",
    "raises", "funding", "invest", "series-a", "series-b", "series-c",
    "secures", "closes", "growth-capital", "round",
]

NON_ARTICLE_SEGMENTS = ["/category/", "/tag/", "/search", "/pub/dir/", "/profile/"]
NEWS_SEGMENTS = ["/news/", "/press/", "/media/", "/article/", "/stories/"]
NON_ARTICLE_EXTENSIONS = (".pdf", ".jpg", ".png", ".gif", ".txt", ".csv", ".zip")


def _is_blocked_domain(url: str) -> bool:
    """Check if URL belongs to a blocked domain."""
    try:
        domain = urlparse(url.strip()).netloc.lower().removeprefix("www.")
        return any(domain.endswith(d) for d in BLOCKED_DOMAINS)
    except ValueError:
        return False


def score_url_for_deal_relevance(url: str) -> int:
    """Score URL by likelihood of containing M&A deal info (higher = better)."""
    score = 50

    try:
        parsed = urlparse(url.strip())
        domain = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.lower()
    except ValueError:
        return score

    if any(domain.endswith(d) for d in HIGH_VALUE_DOMAINS):
        score += 30
    if any(domain.endswith(d) for d in LOW_VALUE_DOMAINS):
        score -= 40
    if any(kw in path for kw in DEAL_PATH_KEYWORDS):
        score += 20
    if path in ("", "/", "/index.html", "/index.htm"):
        score -= 30
    if any(seg in path for seg in NON_ARTICLE_SEGMENTS):
        score -= 20
    if len([s for s in path.split("/") if s]) >= 2:
        score += 5
    if path.endswith(NON_ARTICLE_EXTENSIONS):
        score -= 15
    if any(seg in path for seg in NEWS_SEGMENTS):
        score += 10

    return score


@retry(
    retry=retry_if_exception_type((RateLimitError, requests.ConnectionError, requests.Timeout)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _search_google(company_name: str, investor_name: str) -> List[str]:
    """Search Google Custom Search for deal articles. Returns up to 10 URLs."""
    query = " ".join(filter(None, [company_name, investor_name]))
    if not query:
        return []

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": GOOGLE_API_KEY, "cx": GOOGLE_CX, "q": query, "num": 10},
            timeout=20,
        )
        if resp.status_code == 429:
            raise RateLimitError("Google API rate limited (429)")
        if resp.status_code != 200:
            logger.error("Google API error %d", resp.status_code)
            return []

        items = resp.json().get("items", [])
        return [item["link"] for item in items if item.get("link")]

    except (requests.ConnectionError, requests.Timeout) as e:
        logger.warning("Google Search network error: %s", e)
        raise


def _identify_company_website(urls: List[str], company_name: str) -> Optional[str]:
    """Find the official company website from a URL list by domain matching."""
    if not company_name:
        return None

    clean_name = re.sub(r'[^\w\s-]', '', company_name.lower())
    clean_name = re.sub(r'\s+', '', clean_name)
    for suffix in ["inc", "corp", "corporation", "llc", "ltd", "limited", "group", "holdings"]:
        clean_name = clean_name.replace(suffix, "")

    for url in urls:
        try:
            domain = urlparse(url).netloc.lower().removeprefix("www.")
            if clean_name in domain.replace(".", "").replace("-", ""):
                if not any(lv in domain for lv in LOW_VALUE_DOMAINS):
                    return url
        except ValueError:
            continue

    return None


def find_deal_articles(company_name: str, investor_name: str) -> Dict:
    """
    Find top 3 deal articles for a company-investor pair.

    Returns: {"articles": [{"url": str, "score": int}, ...]}
    """
    if not company_name and not investor_name:
        return {"articles": []}

    urls = _search_google(company_name, investor_name)
    if not urls:
        return {"articles": []}

    # Remove company website and blocked domains from article candidates
    company_website = _identify_company_website(urls, company_name)
    article_urls = [
        u for u in urls
        if u != company_website and not _is_blocked_domain(u)
    ]

    # Score, deduplicate, sort
    seen: set[str] = set()
    scored = []
    for url in article_urls:
        if url in seen:
            continue
        seen.add(url)
        scored.append({"url": url, "score": score_url_for_deal_relevance(url)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"articles": scored[:3]}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python deal_article_finder.py <company_name> <investor_name>")
        sys.exit(1)

    result = find_deal_articles(sys.argv[1], sys.argv[2])
    for i, article in enumerate(result["articles"], 1):
        print(f"{i}. [{article['score']:3d}] {article['url']}")
