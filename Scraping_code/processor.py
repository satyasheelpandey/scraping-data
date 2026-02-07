# processor.py
import logging
from urllib.parse import urlparse

from scraper import crawl_portfolio_page
from llm_extractor import extract_company_seeds
from google_company_search import find_official_company_website
from deal_article_finder import find_deal_articles
from db import insert_portfolio_row

logger = logging.getLogger(__name__)

BAD_WEBSITE_KEYWORDS = [
    "portfolio", "fund", "capital", "partners", "equity",
    "invest", "vc", "ventures", "holdings", "group",
    "kkr", "blackstone", "apollo", "advent",
    "crunchbase", "pitchbook", "bloomberg", "linkedin",
]


def _is_bad_website(url: str) -> bool:
    if not url:
        return True
    return any(k in url.lower() for k in BAD_WEBSITE_KEYWORDS)


def _is_portfolio_domain(company_url: str, portfolio_url: str) -> bool:
    if not company_url:
        return True
    try:
        return urlparse(company_url).netloc.lower() == urlparse(portfolio_url).netloc.lower()
    except ValueError:
        return True


def process_portfolio_url(
    source_url: str,
    investor_name: str,
    investor_website: str,
    csv_writer=None,
) -> bool:
    try:
        print(f"\n Processing portfolio URL: {source_url}")

        _, anchors, blocks, dom_chunks, embedded_json = crawl_portfolio_page(source_url)

        seeds = extract_company_seeds(
            source_url=source_url,
            investor_name=investor_name,
            anchors=anchors,
            blocks=blocks,
            dom_chunks=dom_chunks,
            embedded_json=embedded_json,
        )

        if not seeds:
            print("   No companies found by LLM")
            return False

        for seed in seeds:
            seed.investor_name = investor_name

            # --- company website lookup ---
            needs_google = (
                not seed.company_website
                or _is_bad_website(seed.company_website)
                or _is_portfolio_domain(seed.company_website, source_url)
            )

            if needs_google:
                print(f"   Google Search for: {seed.company_name}")
                site = find_official_company_website(seed.company_name)
                if site and not _is_bad_website(site) and not _is_portfolio_domain(site, source_url):
                    seed.company_website = site
                else:
                    seed.company_website = ""

            # --- deal article discovery ---
            articles = ["", "", ""]
            try:
                result = find_deal_articles(
                    company_name=seed.company_name,
                    investor_name=investor_name,
                )
                for i, article in enumerate(result.get("articles", [])[:3]):
                    articles[i] = article["url"]
            except Exception as e:
                print(f"   [DEAL LINK ERROR] {seed.company_name}: {e}")

            # --- build final record ---
            record = {
                "source_url": source_url,
                "investor_name": investor_name,
                "investor_website": investor_website,
                "company_name": seed.company_name,
                "company_website": seed.company_website,
                "article_1": articles[0],
                "article_2": articles[1],
                "article_3": articles[2],
            }

            insert_portfolio_row(record)

            if csv_writer:
                csv_writer.writerow(record)

            print(f"   Saved: {record['company_name']} | articles: {sum(1 for a in articles if a)}")

        print(f"   Done portfolio: {source_url}")
        return True

    except Exception as e:
        logger.exception(f"Error processing {source_url}: {e}")
        return False
