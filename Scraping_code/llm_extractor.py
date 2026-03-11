# llm_extractor.py
import logging
import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from schema import CompanySeed
from utils.json_repair import repair_json

logger = logging.getLogger(__name__)

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing in .env")

client = OpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o-mini"

NAME_FIELDS = {"name", "companyName", "company_name", "title", "companyname"}
SKIP_FIELDS = {"_createdAt", "_updatedAt", "_rev", "_id", "_key", "_system", "_type"}


def _normalize_website(url: str) -> str:
    """Ensure https:// prefix on URLs."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url.replace("http://", "https://")
    return "https://" + url


def _clean_json_array(text: str) -> List[Dict]:
    fixed = repair_json(text)
    try:
        data = json.loads(fixed)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def _extract_records_from_json(data: Any, depth: int = 0) -> List[str]:
    """Recursively find company-like records in nested JSON and return as text blocks."""
    records: List[str] = []
    if depth > 8:
        return records

    if isinstance(data, dict):
        for v in data.values():
            records.extend(_extract_records_from_json(v, depth + 1))
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        has_name = any(k in data[0] for k in NAME_FIELDS)
        if has_name:
            for item in data:
                parts = []
                for k, v in item.items():
                    if k in SKIP_FIELDS:
                        continue
                    if isinstance(v, str) and v.strip():
                        parts.append(f"{k}: {v}")
                if parts:
                    records.append(" | ".join(parts))
        else:
            for item in data:
                if isinstance(item, dict):
                    records.extend(_extract_records_from_json(item, depth + 1))

    return records


@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
    wait=wait_exponential(multiplier=2, min=4, max=120),
    stop=stop_after_attempt(3),
    before_sleep=lambda retry_state: logger.warning(
        "OpenAI rate limited, retrying in %ds...", retry_state.next_action.sleep
    ),
)
def _call_openai(system_prompt: str, user_content: str):
    return client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=8000,
    )


def extract_company_seeds(
    source_url: str,
    investor_name: str,
    anchors: List[Dict],
    blocks: List[str],
    dom_chunks: List[str],
    embedded_json: List[Dict[str, Any]],
) -> List[CompanySeed]:
    """Extract company names and websites from crawled portfolio page data."""
    anchor_hints = []
    for a in anchors:
        text = (a.get("text") or "").strip()
        href = (a.get("href") or "").strip()

        if not text and not href:
            continue

        anchor_hints.append({
            "text": text,
            "hint": href.strip("/").split("/")[-1] if "/" in href else ""
        })

    # Extract structured records from embedded JSON (SPA data, script tags)
    json_records: List[str] = []
    for obj in embedded_json:
        json_records.extend(_extract_records_from_json(obj))

    payload: Dict[str, Any] = {
        "anchor_hints": anchor_hints[:300],
        "blocks": blocks[:250],
        "dom_chunks": dom_chunks[:80],
    }
    if json_records:
        payload["structured_data"] = json_records[:200]

    system_prompt = (
        "You are an expert portfolio page parser.\n\n"

        "GOAL:\n"
        "Extract ALL portfolio company names that appear on this investor page.\n\n"

        "IMPORTANT:\n"
        "- Companies may appear as cards, tiles, grids, tables, or repeated links\n"
        "- Many companies are represented only by anchor links\n"
        "- Anchor text OR anchor hint may represent the company name\n"
        "- Repeated anchor patterns usually indicate portfolio companies\n"
        "- structured_data contains records extracted from the page's data layer "
        "(look for name, companyName, or title fields for company names, "
        "and website fields for URLs)\n\n"

        "STRICT RULES:\n"
        "- Do NOT invent companies\n"
        "- Do NOT guess from context alone\n"
        "- If a company is not clearly present, exclude it\n"
        "- Deduplicate aggressively\n\n"

        "OUTPUT FORMAT:\n"
        "Return ONLY a JSON ARRAY:\n"
        "[\n"
        "  {\"company_name\": \"Company Name\", \"company_website\": \"\"}\n"
        "]\n\n"

        "If website is unknown, use empty string.\n"
        "NO explanations. NO extra text."
    )

    resp = _call_openai(system_prompt, json.dumps(payload, ensure_ascii=False))

    raw = _clean_json_array(resp.choices[0].message.content or "[]")

    seeds: List[CompanySeed] = []
    seen = set()

    for item in raw:
        name = (item.get("company_name") or "").strip()
        raw_site = (item.get("company_website") or "").strip()
        site = _normalize_website(raw_site)

        if not name:
            continue

        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        seeds.append(
            CompanySeed(
                source_url=source_url,
                investor_name=investor_name,
                company_name=name,
                company_website=site,
            )
        )

    return seeds
