import time
import os
import requests
from typing import List, Dict
from urllib.parse import quote, urlparse
from dotenv import load_dotenv


# ==================================================
# ENV
# ==================================================

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_DEAL_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_DEAL_CX")

if not GOOGLE_API_KEY or not GOOGLE_CX:
    raise RuntimeError("GOOGLE_DEAL_API_KEY or GOOGLE_DEAL_CX missing in .env")


REQUEST_DELAY = 1.0


# High-signal keywords
PRIORITY_WORDS = {
    "news": 10,
    "transaction": 10,
    "deal": 8,
    "acquisition": 8,
    "acquired": 8,
    "merger": 8,
}


# ==================================================
# SCORING
# ==================================================

def score_domain(link: str, query_words: List[str]) -> int:
    score = 0

    try:
        parsed = urlparse(link)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        url_lower = link.lower()

        # Match company words in domain OR path
        for w in query_words:
            if w in domain:
                score += 6
            if w in path:
                score += 3

        # High-intent words
        for p, weight in PRIORITY_WORDS.items():
            if p in url_lower:
                score += weight

    except Exception:
        pass

    return score


# ==================================================
# GOOGLE SEARCH
# ==================================================

def google_search(query: str, max_results: int = 10) -> List[str]:
    url = (
        "https://www.googleapis.com/customsearch/v1"
        f"?key={GOOGLE_API_KEY}"
        f"&cx={GOOGLE_CX}"
        f"&q={quote(query)}"
    )

    resp = requests.get(url, timeout=20)

    if resp.status_code != 200:
        print(f"[GOOGLE ERROR] {resp.status_code}: {resp.text}")
        return []

    data = resp.json()

    items = data.get("items", [])
    if not items:
        print(f"[GOOGLE] No results for query: {query}")

    links = []
    for item in items[:max_results]:
        link = item.get("link")
        if link:
            links.append(link)

    return links


# ==================================================
# PUBLIC API (PIPELINE CALLS THIS)
# ==================================================

def find_ranked_deal_links(
    target: str,
    acquirer: str,
    top_k: int = 5,
) -> List[Dict]:

    query = f"{target} {acquirer}"
    print(f"🔁 Google Search API used for: {query}")

    query_words = query.lower().split()

    links = google_search(query)

    if not links:
        return []

    scored = []
    for link in links:
        s = score_domain(link, query_words)
        scored.append({
            "url": link,
            "score": s,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    time.sleep(REQUEST_DELAY)

    return scored[:top_k]


# ==================================================
# CLI TEST
# ==================================================

if __name__ == "__main__":
    results = find_ranked_deal_links(
        target="Happy Socks",
        acquirer="Palamon",
        top_k=5,
    )

    for r in results:
        print(r)
    print("✅ Test completed.")
