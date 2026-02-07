# llm_extractor.py
import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI

from schema import PortfolioCsvRow, CompanySeed, PageDoc
from utils.url_normalizer import normalize_url
from utils.json_repair import repair_json


# --------------------------------------------------
# ENV
# --------------------------------------------------

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing in .env")

client = OpenAI(api_key=OPENAI_API_KEY)

MODEL_FAST = "gpt-4o-mini"
MODEL_DEEP = "gpt-4o-mini"  # Changed from gpt-4o (not accessible)




def normalize_website_strict(url: str) -> str:
    """
    Guarantees https:// format for domains.
    """
    if not url:
        return ""

    url = url.strip()

    # already has scheme
    if url.startswith("http://") or url.startswith("https://"):
        return url.replace("http://", "https://")

    # domain only
    return "https://" + url


# --------------------------------------------------
# JSON CLEANERS (UNCHANGED)
# --------------------------------------------------

def _clean_json_array(text: str) -> List[Dict]:
    fixed = repair_json(text)
    try:
        data = json.loads(fixed)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _clean_json_object(text: str) -> Dict:
    fixed = repair_json(text)
    try:
        data = json.loads(fixed)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# --------------------------------------------------
# SEED EXTRACTION (HIGH RECALL, SAFE)
# --------------------------------------------------

def extract_company_seeds(
    source_url: str,
    investor_name: str,
    page_text: str,
    anchors: List[Dict],
    blocks: List[str],
    dom_chunks: List[str],
    embedded_json: List[Dict[str, Any]],
) -> List[CompanySeed]:
    """
    Same function signature.
    Higher recall using stronger LLM signals.
    """

    # -----------------------------
    # Anchor hints (NO URL parsing logic)
    # -----------------------------
    anchor_hints = []
    for a in anchors:
        text = (a.get("text") or "").strip()
        href = (a.get("href") or "").strip()

        if not text and not href:
            continue

        anchor_hints.append({
            "text": text,
            "hint": href.split("/")[-1] if "/" in href else ""
        })

    payload = {
        # strongest signals first
        "anchor_hints": anchor_hints[:300],

        # visible content
        "blocks": blocks[:250],

        # tables / grids
        "dom_chunks": dom_chunks[:80],
    }

    system_prompt = (
        "You are an expert portfolio page parser.\n\n"

        "GOAL:\n"
        "Extract ALL portfolio company names that appear on this investor page.\n\n"

        "IMPORTANT:\n"
        "- Companies may appear as cards, tiles, grids, tables, or repeated links\n"
        "- Many companies are represented only by anchor links\n"
        "- Anchor text OR anchor hint may represent the company name\n"
        "- Repeated anchor patterns usually indicate portfolio companies\n\n"

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

    resp = client.chat.completions.create(
        model=MODEL_FAST,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.0,
        max_tokens=3500,
    )

    raw = _clean_json_array(resp.choices[0].message.content or "[]")

    seeds: List[CompanySeed] = []
    seen = set()

    for item in raw:
        name = (item.get("company_name") or "").strip()
        raw_site = (item.get("company_website") or "").strip()
        site = normalize_website_strict(raw_site)

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


# --------------------------------------------------
# DOC SELECTION (UNCHANGED)
# --------------------------------------------------

def select_company_docs(
    seed: CompanySeed,
    docs_by_url: Dict[str, PageDoc],
    max_docs: int = 25,
) -> List[Dict[str, Any]]:

    name = seed.company_name.lower()
    selected: List[PageDoc] = []

    for doc in docs_by_url.values():
        if name in doc.url.lower() or name in doc.text.lower():
            selected.append(doc)
        if len(selected) >= max_docs:
            break

    return [
        {
            "url": d.url,
            "type": d.doc_type,
            "text": d.text,
            "embedded_json": d.embedded_json,
        }
        for d in selected
    ]


# --------------------------------------------------
# DEEP FUSION (UNCHANGED)
# --------------------------------------------------

def fuse_deep_profile(
    seed: CompanySeed,
    documents: List[Dict[str, Any]],
) -> PortfolioCsvRow:

    system_prompt = (
        "You normalize a company website.\n\n"
        "RULES:\n"
        "- Use ONLY provided documents\n"
        "- Do NOT guess\n"
        "- If multiple websites appear, pick the most official\n"
        "- Otherwise return empty string\n\n"
        "Return ONLY JSON:\n"
        "{ \"company_website\": \"\" }"
    )

    resp = client.chat.completions.create(
        model=MODEL_DEEP,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({
                "seed": seed.model_dump(),
                "documents": documents[:15],
            }, ensure_ascii=False)},
        ],
        temperature=0.0,
        max_tokens=1200,
    )

    data = _clean_json_object(resp.choices[0].message.content or "{}")

    website = normalize_url(
        seed.source_url,
        data.get("company_website", "")
    ) or seed.company_website

    return PortfolioCsvRow(
        source_url=seed.source_url,
        investor_name=seed.investor_name,
        company_name=seed.company_name,
        company_website=website or "",
    )
