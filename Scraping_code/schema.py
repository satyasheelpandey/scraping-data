# schema.py
from pydantic import BaseModel
from typing import List, Any

class PageDoc(BaseModel):
    url: str
    doc_type: str
    text: str
    embedded_json: List[Any] = []

class CompanySeed(BaseModel):
    source_url: str
    investor_name: str
    company_name: str
    company_website: str = ""
    keywords: List[str] = []   # NEW: keywords from scraper/filter discovery

class PortfolioCsvRow(BaseModel):
    source_url: str
    investor_name: str
    company_name: str
    company_website: str
    keywords: List[str] = []   # NEW: keywords for output
