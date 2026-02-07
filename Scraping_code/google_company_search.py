# google_company_search.py
import os
import requests
from urllib.parse import urlparse

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

def find_official_company_website(company_name: str) -> dict:
    """
    Returns dict: { 'company_website': str, 'title': str, 'snippet': str }
    or {} if nothing found.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return {}

    print(f"🌐 Google Search API used for: {company_name}")

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
        print(f"[GOOGLE ERROR] {e}")
        return {}

    for item in data.get("items", []):
        link = item.get("link", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        domain = urlparse(link).netloc.lower()
        if any(k in domain for k in REJECT_KEYWORDS):
            continue
        # Accept first likely official domain
        return {"company_website": link, "title": title, "snippet": snippet}
    return {}
