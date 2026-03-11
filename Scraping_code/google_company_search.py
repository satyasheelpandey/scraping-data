# google_company_search.py
import os
import logging
import requests
from urllib.parse import urlparse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

REJECT_KEYWORDS = [
    "invest", "portfolio", "fund", "capital", "partners", "equity",
    "ventures", "holdings", "group", "kkr", "blackstone", "apollo",
    "crunchbase", "pitchbook", "linkedin", "bloomberg", "wikipedia",
    "glassdoor", "angel.co", "startup", "techcrunch",
]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
    logger.warning("GOOGLE_API_KEY/GOOGLE_CSE_ID not set; google fallback disabled.")


def _is_valid_company_domain(
    website: str, company_name: str, entity_name: str
) -> bool:
    """Check if a website domain plausibly matches the company name."""
    domain = urlparse(website).netloc.lower()

    if any(k in domain for k in REJECT_KEYWORDS):
        return False

    company_clean = company_name.lower().replace(" ", "").replace("-", "")
    domain_clean = domain.replace("www.", "").replace(".com", "").replace(".net", "").replace(".org", "")
    entity_clean = entity_name.lower().replace(" ", "").replace("-", "")

    return (
        company_clean in domain_clean
        or domain_clean in company_clean
        or company_clean == entity_clean
    )


@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(3),
    reraise=False,
)
def _try_knowledge_graph(company_name: str) -> str:
    """Try Knowledge Graph API. Returns company website URL or ''."""
    if not GOOGLE_API_KEY:
        return ""

    try:
        resp = requests.get(
            "https://kgsearch.googleapis.com/v1/entities:search",
            params={"key": GOOGLE_API_KEY, "query": company_name, "limit": 5},
            timeout=10,
        )
        if resp.status_code == 429:
            logger.warning("Knowledge Graph rate limited, retrying...")
            raise requests.ConnectionError("Rate limited (429)")
        resp.raise_for_status()

        for item in resp.json().get("itemListElement", []):
            result = item.get("result", {})
            entity_name = result.get("name", "")
            for website in [
                result.get("url", ""),
                result.get("detailedDescription", {}).get("url", ""),
            ]:
                if website and _is_valid_company_domain(website, company_name, entity_name):
                    logger.info("Knowledge Graph verified: %s", website)
                    return website

    except requests.HTTPError as e:
        logger.warning("Knowledge Graph HTTP error: %s", e)

    return ""


@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(3),
    reraise=False,
)
def _try_custom_search(company_name: str) -> str:
    """Fallback to Custom Search API. Returns company website URL or ''."""
    if not GOOGLE_CSE_ID:
        return ""

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": company_name, "num": 5},
            timeout=15,
        )
        if resp.status_code == 429:
            logger.warning("Custom Search rate limited, retrying...")
            raise requests.ConnectionError("Rate limited (429)")
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        logger.warning("Custom Search HTTP error: %s", e)
        return ""

    for item in data.get("items", []):
        link = item.get("link", "")
        domain = urlparse(link).netloc.lower()
        if not any(k in domain for k in REJECT_KEYWORDS):
            return link

    return ""


def find_official_company_website(company_name: str) -> str:
    """
    Find official company website using Google APIs.
    Returns the website URL or ''.
    """
    if not GOOGLE_API_KEY:
        return ""

    logger.info("Google API for: %s", company_name)

    result = _try_knowledge_graph(company_name)
    if result:
        return result

    logger.info("Fallback to Custom Search for: %s", company_name)
    return _try_custom_search(company_name)
