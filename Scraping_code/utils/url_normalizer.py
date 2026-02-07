# utils/url_normalizer.py
from urllib.parse import urljoin, urlparse

def normalize_url(base: str, href: str) -> str:
    """
    Normalize href relative to base. Return empty string when invalid.
    """
    if not href:
        return ""
    href = href.strip()
    if href.startswith("//"):
        href = "http:" + href
    if href.startswith("http://") or href.startswith("https://"):
        return href
    try:
        return urljoin(base, href)
    except Exception:
        return ""
