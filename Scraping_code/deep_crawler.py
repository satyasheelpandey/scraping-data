# deep_crawler.py
import asyncio
from collections import deque
from typing import Dict, Set
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler

from schema import PageDoc
from utils.url_normalizer import normalize_url

MAX_PAGES_PER_DOMAIN = 800
MAX_DEPTH_PER_DOMAIN = 6

async def _crawl_domain_async(seed_url: str) -> Dict[str, PageDoc]:
    parsed = urlparse(seed_url)
    domain = parsed.netloc
    visited: Set[str] = set()
    queue = deque([(seed_url, 0)])
    docs: Dict[str, PageDoc] = {}

    async with AsyncWebCrawler() as crawler:
        while queue and len(visited) < MAX_PAGES_PER_DOMAIN:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            if depth > MAX_DEPTH_PER_DOMAIN:
                continue
            try:
                print(f"[CRAWL] depth={depth} :: {url}")
                res = await crawler.arun(url=url)
                markdown = res.markdown or ""
                html = res.html or ""
                text = " ".join((markdown or "").split())
                if len(text) < 30:
                    text = " ".join((html or "").split())[:2000]
                embedded = []
                # Basic: not doing heavy parsing to keep performance; can be extended
                docs[url] = PageDoc(url=url, doc_type="other", text=text[:80000], embedded_json=embedded)
                for l in (res.links or []):
                    href = getattr(l, "href", None)
                    if not href:
                        continue
                    norm = normalize_url(url, href)
                    if not norm:
                        continue
                    p = urlparse(norm)
                    if p.netloc != domain:
                        continue
                    if norm not in visited:
                        queue.append((norm, depth + 1))
            except Exception as e:
                print(f"[DEEP CRAWL ERROR] {url}: {e}")
                continue
    return docs

def crawl_domain(seed_url: str) -> Dict[str, PageDoc]:
    return asyncio.run(_crawl_domain_async(seed_url))
