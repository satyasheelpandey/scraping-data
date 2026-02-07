# scraper.py
import asyncio
import json
from typing import List, Tuple, Dict, Any

import requests
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


CRAWL_CONFIG = CrawlerRunConfig(
    wait_until="networkidle",
    delay_before_return_html=3.0,
    scan_full_page=True,
    page_timeout=30000,
)


def _try_spa_data_endpoints(url: str) -> List[Dict[str, Any]]:
    """Probe common SPA data endpoints (Gatsby, Next.js, etc.) for structured JSON."""
    parsed = urlparse(url)
    path = parsed.path.strip("/") or "index"
    base = f"{parsed.scheme}://{parsed.netloc}"

    endpoints = [
        f"{base}/page-data/{path}/page-data.json",  # Gatsby
    ]

    results = []
    for endpoint in endpoints:
        try:
            resp = requests.get(endpoint, timeout=5)
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and "json" in ct:
                results.append(resp.json())
                print(f"  SPA data found: {endpoint}")
        except requests.RequestException:
            pass

    return results


def _extract_from_html(base_url: str, html: str, markdown: str):
    soup = BeautifulSoup(html or "", "html.parser")
    page_text = " ".join((markdown or "").split())

    anchors = []
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        if href.startswith("/"):
            href = urljoin(base_url, href)
        # Use image alt text as fallback when link text is empty/short
        text = a.get_text(" ", strip=True)
        if len(text) < 3:
            img = a.find("img")
            if img and img.get("alt"):
                text = img["alt"]
        anchors.append({
            "text": text,
            "href": href,
        })

    blocks = []
    for tag in soup.find_all(["article", "li", "section", "div"]):
        txt = tag.get_text(" ", strip=True)
        if 30 < len(txt) < 1500:
            blocks.append(txt)

    dom_chunks = [
        table.get_text(" ", strip=True)
        for table in soup.find_all("table")
    ]

    embedded_json: List[Dict] = []
    for script in soup.find_all("script"):
        if script.string and "{" in script.string:
            try:
                embedded_json.append(json.loads(script.string))
            except (json.JSONDecodeError, ValueError):
                pass

    return page_text, anchors, blocks, dom_chunks, embedded_json


async def _crawl(url: str) -> List[Tuple[str, str]]:
    """Crawl a URL with JS rendering and return (html, markdown) snapshots."""
    snapshots: List[Tuple[str, str]] = []
    async with AsyncWebCrawler() as crawler:
        try:
            res = await crawler.arun(url=url, config=CRAWL_CONFIG)
            snapshots.append((res.html or "", res.markdown or ""))
        except (TimeoutError, RuntimeError, OSError) as e:
            print(f"[SCRAPER] Crawl failed: {e}")
    return snapshots


def crawl_portfolio_page(url: str):
    try:
        snapshots = asyncio.run(_crawl(url))
    except Exception as e:
        print(f"[SCRAPER ERROR] {url}: {e}")
        return "", [], [], [], []

    all_text = []
    all_anchors = []
    all_blocks = []
    all_chunks = []
    all_json = []

    for html, markdown in snapshots:
        text, anchors, blocks, chunks, embedded = _extract_from_html(url, html, markdown)
        if text:
            all_text.append(text)
        all_anchors.extend(anchors)
        all_blocks.extend(blocks)
        all_chunks.extend(chunks)
        all_json.extend(embedded)

    # Probe common SPA data endpoints for structured JSON
    spa_data = _try_spa_data_endpoints(url)
    all_json.extend(spa_data)

    return (
        " ".join(all_text),
        list({(a["text"], a["href"]): a for a in all_anchors}.values()),
        list(set(all_blocks)),
        list(set(all_chunks)),
        all_json,
    )
