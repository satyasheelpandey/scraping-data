# schema.py
from typing import Optional

from pydantic import BaseModel


class CompanySeed(BaseModel):
    source_url: str
    investor_name: str
    company_name: str
    company_website: str = ""
    company_status: str = ""
    strategy: str = ""


class DealInfo(BaseModel):
    announcement_date: Optional[str] = None
    deal_type: Optional[str] = None
    deal_value: Optional[float] = None
    deal_value_text: Optional[str] = None
    currency: Optional[str] = None
    deal_stage: Optional[str] = None
    strategic_rationale: Optional[str] = None
    source_article_url: Optional[str] = None
