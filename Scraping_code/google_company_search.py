# google_company_search.py
import os
import requests
from urllib.parse import urlparse
from typing import Dict

REJECT_KEYWORDS = [
    "invest", "portfolio", "fund", "capital", "partners", "equity",
    "ventures", "holdings", "group", "kkr", "blackstone", "apollo",
    "crunchbase", "pitchbook", "linkedin", "bloomberg", "wikipedia",
    "glassdoor", "angel.co", "startup", "techcrunch"
]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
    print("WARNING: GOOGLE_API_KEY/GOOGLE_CSE_ID not set; google fallback disabled.")


def _try_knowledge_graph(company_name: str) -> Dict:
    """
    Try Google Knowledge Graph API first for verified entity data.

    Returns dict with company_website if found, else {}.
    Knowledge Graph provides structured, verified company information.
    """
    if not GOOGLE_API_KEY:
        return {}

    url = "https://kgsearch.googleapis.com/v1/entities:search"
    params = {
        "key": GOOGLE_API_KEY,
        "query": company_name,
        "limit": 5,
        # Note: removed 'types' parameter - API works better without it
        # and automatically prioritizes Organization entities
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Parse Knowledge Graph results
        for item in data.get("itemListElement", []):
            result = item.get("result", {})
            entity_name = result.get("name", "").lower()

            # Get official URL from Knowledge Graph
            website = result.get("url", "")
            if website:
                domain = urlparse(website).netloc.lower()

                # Skip if it's an aggregator/investor site
                if any(k in domain for k in REJECT_KEYWORDS):
                    continue

                # Validate: domain should contain company name or vice versa
                # This catches cases like "Salesforce" -> "herontower.com" (wrong!)
                company_clean = company_name.lower().replace(" ", "").replace("-", "")
                domain_clean = domain.replace("www.", "").replace(".com", "").replace(".net", "").replace(".org", "")
                entity_clean = entity_name.replace(" ", "").replace("-", "")

                # Check if company name is in domain or entity name matches
                if (company_clean in domain_clean or
                    domain_clean in company_clean or
                    company_clean == entity_clean):

                    print(f"✓ Knowledge Graph verified: {website}")
                    return {
                        "company_website": website,
                        "title": result.get("name", ""),
                        "snippet": result.get("description", ""),
                        "source": "knowledge_graph"
                    }

        # Also check detailedDescription for website URLs
        for item in data.get("itemListElement", []):
            result = item.get("result", {})
            entity_name = result.get("name", "").lower()
            detailed = result.get("detailedDescription", {})
            website = detailed.get("url", "")

            if website:
                domain = urlparse(website).netloc.lower()
                if any(k in domain for k in REJECT_KEYWORDS):
                    continue

                # Same validation as above
                company_clean = company_name.lower().replace(" ", "").replace("-", "")
                domain_clean = domain.replace("www.", "").replace(".com", "").replace(".net", "").replace(".org", "")
                entity_clean = entity_name.replace(" ", "").replace("-", "")

                if (company_clean in domain_clean or
                    domain_clean in company_clean or
                    company_clean == entity_clean):

                    print(f"✓ Knowledge Graph (detailed) verified: {website}")
                    return {
                        "company_website": website,
                        "title": result.get("name", ""),
                        "snippet": result.get("description", ""),
                        "source": "knowledge_graph"
                    }

    except Exception as e:
        print(f"[KNOWLEDGE GRAPH] {e}")

    return {}


def _try_custom_search(company_name: str) -> Dict:
    """
    Fallback to Google Custom Search API.

    Returns dict with company_website if found, else {}.
    """
    if not GOOGLE_CSE_ID:
        return {}

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": company_name,
        "num": 5,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[CUSTOM SEARCH ERROR] {e}")
        return {}

    for item in data.get("items", []):
        link = item.get("link", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        domain = urlparse(link).netloc.lower()

        if any(k in domain for k in REJECT_KEYWORDS):
            continue

        # Accept first likely official domain
        return {
            "company_website": link,
            "title": title,
            "snippet": snippet,
            "source": "custom_search"
        }

    return {}


def find_official_company_website(company_name: str) -> dict:
    """
    Find official company website using Google APIs.

    Strategy:
    1. Try Knowledge Graph API first (verified, structured data)
    2. Fallback to Custom Search API if needed

    Returns dict: {
        'company_website': str,
        'title': str,
        'snippet': str,
        'source': 'knowledge_graph' or 'custom_search'
    } or {} if nothing found.
    """
    if not GOOGLE_API_KEY:
        return {}

    print(f"🌐 Google API used for: {company_name}")

    # Try Knowledge Graph first (more reliable)
    result = _try_knowledge_graph(company_name)
    if result:
        return result

    # Fallback to Custom Search
    print(f"   → Fallback to Custom Search")
    result = _try_custom_search(company_name)
    if result:
        return result

    return {}
