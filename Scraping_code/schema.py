# schema.py
from pydantic import BaseModel


class CompanySeed(BaseModel):
    source_url: str
    investor_name: str
    company_name: str
    company_website: str = ""
