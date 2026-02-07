# utils/investor.py
from urllib.parse import urlparse

def extract_investor_name(url: str) -> str:
    """
    Derive investor/fund name from the input portfolio URL.
    Simple heuristic: domain label → Title Case.
    """
    if not url:
        return ""
    net = urlparse(url).netloc or url
    net = net.replace("www.", "")
    label = net.split(".")[0]
    return label.replace("-", " ").replace("_", " ").title()
