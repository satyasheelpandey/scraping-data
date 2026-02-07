# scraper.py
import asyncio
import json
import os
from typing import List, Tuple, Set

from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


# ==================================================
# GLOBAL KEYWORD STORE (UNCHANGED)
# ==================================================

KEYWORD_FILE = "global_keywords.json"
KEYWORDS_FILE = "keywords.json"

GLOBAL_KEYWORDS: Set[str] = set()


def load_global_keywords() -> Set[str]:
    global GLOBAL_KEYWORDS

    if GLOBAL_KEYWORDS:
        return GLOBAL_KEYWORDS

    if not os.path.exists(KEYWORD_FILE):
        GLOBAL_KEYWORDS = set()
        return GLOBAL_KEYWORDS

    try:
        with open(KEYWORD_FILE, "r", encoding="utf-8") as f:
            GLOBAL_KEYWORDS = set(json.load(f))
    except Exception:
        GLOBAL_KEYWORDS = set()

    return GLOBAL_KEYWORDS



def save_global_keywords(keywords: Set[str]):
    global GLOBAL_KEYWORDS
    GLOBAL_KEYWORDS.update(keywords)

    with open(KEYWORD_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(GLOBAL_KEYWORDS), f, indent=2, ensure_ascii=False)


# ==================================================
# NEW: KEYWORDS.JSON SAVE (ADDITIVE ONLY)
# ==================================================

def _save_keywords_to_file(new_keywords: Set[str]):
    """
    Append & deduplicate keywords into keywords.json
    """
    if not new_keywords:
        return

    existing = set()

    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    existing.update(data)
        except Exception:
            pass

    existing.update(new_keywords)

    try:
        with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(existing), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[KEYWORDS SAVE ERROR] {e}")


# ==================================================
# HTML EXTRACTION (UNCHANGED)
# ==================================================

def _extract_from_html(base_url: str, html: str, markdown: str):
    soup = BeautifulSoup(html or "", "html.parser")
    page_text = " ".join((markdown or "").split())

    logo_urls = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if src.startswith("/"):
            src = urljoin(base_url, src)
        if "logo" in src.lower():
            logo_urls.append(src)

    anchors = []
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        if href.startswith("/"):
            href = urljoin(base_url, href)
        anchors.append({
            "text": a.get_text(" ", strip=True),
            "href": href,
        })

    blocks = []
    for tag in soup.find_all(["article", "li", "section", "div"]):
        txt = tag.get_text(" ", strip=True)
        if 30 < len(txt) < 1500:
            blocks.append(txt)

    dom_chunks = []
    for table in soup.find_all("table"):
        dom_chunks.append(table.get_text(" ", strip=True))

    embedded_json = []
    for script in soup.find_all("script"):
        if script.string and "{" in script.string:
            try:
                embedded_json.append(json.loads(script.string))
            except Exception:
                pass

    return page_text, logo_urls, anchors, blocks, dom_chunks, embedded_json, soup


# ==================================================
# DOM FILTER KEYWORD EXTRACTION (UNCHANGED)
# ==================================================

def extract_dom_filter_keywords(soup: BeautifulSoup) -> Set[str]:
    keywords = set()

    for option in soup.select("select option"):
        text = option.get_text(strip=True).lower()
        if 2 < len(text) < 40:
            keywords.add(text)

    for inp in soup.select("input[type=checkbox], input[type=radio]"):
        label = soup.find("label", attrs={"for": inp.get("id")})
        if label:
            text = label.get_text(strip=True).lower()
            if 2 < len(text) < 40:
                keywords.add(text)

    for container in soup.select(".filter, .filters, .facet, .portfolio-filter"):
        for a in container.find_all("a"):
            text = a.get_text(strip=True).lower()
            if 2 < len(text) < 40:
                keywords.add(text)

    return keywords


# ==================================================
# FILTER URL DISCOVERY (UNCHANGED)
# ==================================================

def _discover_filter_urls(
    base_url: str,
    html: str,
    global_keywords: Set[str],
) -> Set[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    base_domain = urlparse(base_url).netloc

    filter_urls: Set[str] = set()

    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue

        href_lower = href.lower()

        # this link does not contain any of the global keywords
        
        
        
        

        if not any(k in href_lower for k in global_keywords):
            continue

        full_url = urljoin(base_url, href)

        try:
            if urlparse(full_url).netloc != base_domain:
                continue
        except Exception:
            continue

        filter_urls.add(full_url)

    return filter_urls


# ==================================================
# ASYNC CRAWL (MINIMAL ADDITION ONLY)
# ==================================================

async def _crawl_all_states(url: str):
    snapshots: List[Tuple[str, str]] = []

    global_keywords = load_global_keywords()

    async with AsyncWebCrawler() as crawler:
        try:
            res = await crawler.arun(url=url)
            snapshots.append((res.html or "", res.markdown or ""))
        except Exception as e:
            print(f"[SCRAPER] Base crawl failed: {e}")
            return snapshots, global_keywords

        soup = BeautifulSoup(res.html or "", "html.parser")
        new_keywords = extract_dom_filter_keywords(soup)

        if new_keywords:
            print(f"➕ New DOM keywords found: {sorted(new_keywords)}")

        # 🔹 ADDITION: save keywords
        _save_keywords_to_file(new_keywords)

        global_keywords.update(new_keywords)
        save_global_keywords(global_keywords)

        filter_urls = _discover_filter_urls(url, res.html or "", global_keywords)
        filter_urls.discard(url)

        if filter_urls:
            print("🔎 Filter function invoked")

        for f_url in list(filter_urls)[:15]:
            try:
                print(f"   🔹 Crawling filtered state: {f_url}")
                fres = await crawler.arun(url=f_url)
                snapshots.append((fres.html or "", fres.markdown or ""))
            except Exception as e:
                print(f"[SCRAPER] Skipping filtered URL: {f_url} ({e})")

    return snapshots, global_keywords


# ==================================================
# PUBLIC API (UNCHANGED)
# ==================================================

def crawl_portfolio_page(url: str):
    try:
        snapshots, keywords = asyncio.run(_crawl_all_states(url))
    except Exception as e:
        print(f"[SCRAPER ERROR] {url}: {e}")
        return "", [], [], [], [], [], []

    all_text = []
    all_logos = set()
    all_anchors = []
    all_blocks = []
    all_chunks = []
    all_json = []

    for html, markdown in snapshots:
        (
            text,
            logos,
            anchors,
            blocks,
            chunks,
            embedded,
            _,
        ) = _extract_from_html(url, html, markdown)

        if text:
            all_text.append(text)
        all_logos.update(logos)
        all_anchors.extend(anchors)
        all_blocks.extend(blocks)
        all_chunks.extend(chunks)
        all_json.extend(embedded)

    return (
        " ".join(all_text),
        list(all_logos),
        list({(a["text"], a["href"]): a for a in all_anchors}.values()),
        list(set(all_blocks)),
        list(set(all_chunks)),
        all_json,
        sorted(keywords),
    )
