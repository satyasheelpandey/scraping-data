# processor.py
import traceback
from typing import List, Dict, Set
from urllib.parse import urlparse

from scraper import crawl_portfolio_page
from ocr import run_logo_ocr
from llm_extractor import (
    extract_company_seeds,
    select_company_docs,
    fuse_deep_profile,
)
from deep_crawler import crawl_domain
from google_company_search import find_official_company_website
from db import insert_portfolio_row
from schema import CompanySeed, PortfolioCsvRow


# ==================================================
# GLOBAL KEYWORD MEMORY (CRITICAL FIX)
# ==================================================
GLOBAL_FILTER_KEYWORDS: Set[str] = set()


# --------------------------------------------------
# BAD / INVESTOR / AGGREGATOR DOMAIN FILTER
# --------------------------------------------------
BAD_WEBSITE_KEYWORDS = [
    "portfolio", "fund", "capital", "partners", "equity",
    "invest", "vc", "ventures", "holdings", "group",
    "kkr", "blackstone", "apollo", "advent",
    "crunchbase", "pitchbook", "bloomberg", "linkedin",
]


def _is_bad_website(url: str) -> bool:
    if not url:
        return True
    u = url.lower()
    return any(k in u for k in BAD_WEBSITE_KEYWORDS)


def _is_portfolio_domain(company_url: str, portfolio_url: str) -> bool:
    if not company_url:
        return True
    try:
        return urlparse(company_url).netloc.lower() == urlparse(portfolio_url).netloc.lower()
    except Exception:
        return True


# --------------------------------------------------
# KEYWORD MATCHING (SAFE + PRECISE)
# --------------------------------------------------
def _match_keywords_for_seed(
    seed: CompanySeed,
    keywords: Set[str],
    anchors: List[Dict],
    blocks: List[str],
) -> List[str]:
    """
    Match ONLY keywords that are actually relevant to this company
    """
    matched = set()
    site = (seed.company_website or "").lower()
    name = (seed.company_name or "").lower()
    page_text = " ".join(blocks).lower()

    for k in keywords:
        if not k or len(k) < 2:
            continue

        if k in site or k in name or k in page_text:
            matched.add(k)
            continue

        for a in anchors:
            if k in (a.get("href", "") or "").lower() or k in (a.get("text", "") or "").lower():
                matched.add(k)
                break

    return sorted(matched)


# --------------------------------------------------
# MAIN PROCESSOR
# --------------------------------------------------
def process_portfolio_url(
    source_url: str,
    investor_name: str,
    csv_writer=None,
) -> bool:
    global GLOBAL_FILTER_KEYWORDS

    try:
        print(f"\n🔍 Processing portfolio URL: {source_url}")

        # --------------------------------------------------
        # 1️⃣ Crawl portfolio page (DOM FILTER ONLY)
        # --------------------------------------------------
        (
            page_text,
            logo_urls,
            anchors,
            blocks,
            dom_chunks,
            embedded_json,
            dom_filter_keywords,
        ) = crawl_portfolio_page(source_url)

        print(f"🧩 New DOM keywords found: {dom_filter_keywords}")

        # --------------------------------------------------
        # 2️⃣ MERGE KEYWORDS (CRITICAL FIX)
        # --------------------------------------------------
        GLOBAL_FILTER_KEYWORDS.update(dom_filter_keywords or [])
        active_keywords = set(GLOBAL_FILTER_KEYWORDS)

        print(f"🔗 Active keywords: {sorted(active_keywords)}")

        # --------------------------------------------------
        # 3️⃣ OCR
        # --------------------------------------------------
        ocr_results = []
        for img in logo_urls:
            text, conf = run_logo_ocr(img)
            if text:
                ocr_results.append({"text": text, "confidence": conf})

        # --------------------------------------------------
        # 4️⃣ LLM SEED EXTRACTION
        # --------------------------------------------------
        seeds = extract_company_seeds(
            source_url=source_url,
            investor_name=investor_name,
            page_text=page_text,
            anchors=anchors,
            ocr_results=ocr_results,
            blocks=blocks,
            dom_chunks=dom_chunks,
            embedded_json=embedded_json,
        )

        if not seeds:
            print("⚠️ No companies found by LLM")
            return False

        # --------------------------------------------------
        # 5️⃣ Deep crawl once
        # --------------------------------------------------
        docs_by_url = crawl_domain(source_url)

        # --------------------------------------------------
        # 6️⃣ Process companies
        # --------------------------------------------------
        for seed in seeds:
            seed.investor_name = investor_name

            needs_google = (
                not seed.company_website
                or _is_bad_website(seed.company_website)
                or _is_portfolio_domain(seed.company_website, source_url)
            )

            if needs_google:
                print(f"🔁 Google Search API used for: {seed.company_name}")
                g = find_official_company_website(seed.company_name) or {}
                site = g.get("company_website", "")
                if site and not _is_bad_website(site) and not _is_portfolio_domain(site, source_url):
                    seed.company_website = site
                else:
                    seed.company_website = (
                        "website is not found after doing the "
                        "llm extractor and google search api system"
                    )

            # --------------------------------------------------
            # 7️⃣ KEYWORD MATCH (FIXED)
            # --------------------------------------------------
            seed.keywords = _match_keywords_for_seed(
                seed,
                active_keywords,
                anchors,
                blocks,
            )

            # --------------------------------------------------
            # 8️⃣ Deep fusion
            # --------------------------------------------------
            docs = select_company_docs(seed, docs_by_url)
            fused: PortfolioCsvRow = fuse_deep_profile(seed, docs)

            record = {
                "source_url": source_url,
                "investor_name": investor_name,
                "company_name": fused.company_name,
                "company_website": fused.company_website,
                "keywords": seed.keywords,
            }

            insert_portfolio_row(record)

            if csv_writer:
                csv_writer.writerow({
                    **record,
                    "keywords": ",".join(record["keywords"]),
                })

            print(f"💾 Saved company: {record['company_name']} (keywords: {record['keywords']})")

        print(f"🎯 Done portfolio: {source_url}")
        return True

    except Exception as e:
        print(f"❌ Error processing {source_url}: {e}")
        traceback.print_exc()
        return False
