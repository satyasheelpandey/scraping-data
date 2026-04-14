# article_analyzer.py
"""
Article Deal Information Extraction

Fetches article content via crawl4ai (headless browser), extracts deal
details via GPT-4o-mini, and cascades through up to 3 articles until
50%+ of key fields are populated.
"""
import asyncio
import json
import logging
import os
from typing import List, Optional

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from schema import DealInfo

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing in .env")

_client = OpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o-mini"

MAX_ARTICLE_CHARS = 8000

_KEY_FIELDS = (
    "announcement_date",
    "deal_type",
    "deal_value",
    "currency",
    "deal_stage",
    "strategic_rationale",
)

VALID_DEAL_TYPES = {
    "Merger", "Entry-deal", "Add-on", "Carve-out", "P2P",
    "MBI", "MBO", "Funding", "Debt", "Joint-Venture", "Follow-on",
}

_DEAL_TYPE_LOOKUP = {v.lower(): v for v in VALID_DEAL_TYPES}
# Map "acquisition" to "Entry-deal"
_DEAL_TYPE_LOOKUP["acquisition"] = "Entry-deal"

_STRIP_TAGS = ["script", "style", "nav", "footer", "aside", "header"]

_ARTICLE_SELECTORS = [
    "article",
    "main",
    ".article-content",
    ".post-content",
    ".entry-content",
    ".content-body",
    "#content",
]

_ARTICLE_CRAWL_CONFIG = CrawlerRunConfig(
    wait_until="domcontentloaded",
    delay_before_return_html=1.0,
    page_timeout=20000,
)

_SYSTEM_PROMPT = (
    "You are a deal information extraction specialist.\n\n"
    "CONTEXT:\n"
    "The user will provide article text about a deal involving a specific "
    "company and investor. Your job is to extract structured deal details.\n\n"
    "RULES:\n"
    "- Only extract facts explicitly stated in the article\n"
    "- Do NOT invent or assume any values\n"
    "- If a field is not mentioned, return null\n"
    "- For deal_value, return the raw number (e.g. 25000000 not \"$25 million\")\n"
    "- For deal_value_text, return the original text (e.g. \"$25 million\")\n"
    "- For deal_type, use EXACTLY one of: Entry-deal, Merger, "
    "Add-on, Carve-out, P2P, MBI, MBO, Funding, Debt, Joint-Venture, "
    "Follow-on — or null if none match. Use 'Entry-deal' for acquisitions.\n"
    "- For deal_stage, use one of: announced, agreed, completed, terminated, "
    "pending, rumored — or null\n"
    "- For announcement_date, use YYYY-MM-DD format\n"
    "- For strategic_rationale, write 1-3 factual sentences summarizing "
    "why the deal happened\n\n"
    "OUTPUT FORMAT (JSON only):\n"
    "{\n"
    '  "announcement_date": "YYYY-MM-DD or null",\n'
    '  "deal_type": "Entry-deal|Merger|Add-on|Carve-out|P2P|MBI|MBO|Funding|Debt|Joint-Venture|Follow-on or null",\n'
    '  "deal_value": "number or null",\n'
    '  "deal_value_text": "string or null",\n'
    '  "currency": "string or null",\n'
    '  "deal_stage": "string or null",\n'
    '  "strategic_rationale": "string or null"\n'
    "}\n"
)


def _extract_text_from_html(html: str, markdown: str) -> str:
    """Extract readable article text from HTML, preferring markdown when available."""
    # crawl4ai markdown is usually clean — prefer it if substantial
    if markdown and len(markdown.strip()) >= 200:
        return markdown.strip()[:MAX_ARTICLE_CHARS]

    # Fallback: parse HTML with BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")

    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for selector in _ARTICLE_SELECTORS:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(separator=" ", strip=True)
            if len(text) >= 200:
                return text[:MAX_ARTICLE_CHARS]

    body = soup.find("body")
    if body:
        text = body.get_text(separator=" ", strip=True)
        return text[:MAX_ARTICLE_CHARS]

    return ""


async def _crawl_article(url: str) -> str:
    """Crawl a single article URL with crawl4ai and return extracted text."""
    async with AsyncWebCrawler() as crawler:
        res = await crawler.arun(url=url, config=_ARTICLE_CRAWL_CONFIG)
        return _extract_text_from_html(res.html or "", res.markdown or "")


def fetch_article_content(url: str) -> str:
    """Fetch and extract readable text from an article URL using crawl4ai."""
    try:
        return asyncio.run(_crawl_article(url))
    except (TimeoutError, RuntimeError, OSError) as e:
        logger.warning("Crawl failed for %s: %s", url, e)
        return ""


@retry(
    retry=retry_if_exception_type(
        (RateLimitError, APIConnectionError, APITimeoutError)
    ),
    wait=wait_exponential(multiplier=2, min=4, max=120),
    stop=stop_after_attempt(3),
    before_sleep=lambda retry_state: logger.warning(
        "OpenAI rate limited, retrying in %ds...",
        retry_state.next_action.sleep,
    ),
)
def _call_extraction_llm(
    article_text: str, company_name: str, investor_name: str
) -> dict:
    """Call GPT-4o-mini to extract deal information from article text."""
    user_content = (
        f"Company: {company_name}\n"
        f"Investor: {investor_name}\n\n"
        f"Article text:\n{article_text}"
    )

    resp = _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    raw_text = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Malformed JSON from LLM: %s", raw_text[:200])
        return {}


def _compute_population_ratio(deal_info: DealInfo) -> float:
    """Compute fraction of key fields that are non-null (0.0 to 1.0)."""
    populated = sum(
        1
        for field in _KEY_FIELDS
        if getattr(deal_info, field) is not None
    )
    return populated / len(_KEY_FIELDS)


def analyze_deal(
    article_urls: List[str],
    company_name: str,
    investor_name: str,
) -> DealInfo:
    """
    Cascade through article URLs extracting deal info.

    Stops early when 50%+ of key fields are populated.
    Returns the best DealInfo found, or an empty DealInfo.
    """
    best_info: Optional[DealInfo] = None
    best_ratio = 0.0

    for url in article_urls[:3]:
        if not url:
            continue

        try:
            text = fetch_article_content(url)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            continue

        if len(text) < 200:
            continue

        try:
            raw = _call_extraction_llm(text, company_name, investor_name)
        except Exception as e:
            logger.warning("LLM extraction failed for %s: %s", url, e)
            continue

        raw["source_article_url"] = url

        # Normalize deal_type to valid values
        raw_deal_type = raw.get("deal_type")
        if raw_deal_type:
            normalized = _DEAL_TYPE_LOOKUP.get(raw_deal_type.strip().lower())
            raw["deal_type"] = normalized  # None if not in valid set

        # Coerce deal_value to float if present
        if raw.get("deal_value") is not None:
            try:
                raw["deal_value"] = float(raw["deal_value"])
            except (ValueError, TypeError):
                raw["deal_value"] = None

        try:
            info = DealInfo(**{
                k: v for k, v in raw.items()
                if k in DealInfo.model_fields
            })
        except Exception as e:
            logger.warning("DealInfo parse error for %s: %s", url, e)
            continue

        ratio = _compute_population_ratio(info)
        if ratio > best_ratio:
            best_info = info
            best_ratio = ratio

        if ratio >= 0.5:
            break

    return best_info or DealInfo()
