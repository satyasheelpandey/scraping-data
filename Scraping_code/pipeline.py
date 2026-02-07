# pipeline.py
import csv
import ipaddress
import logging
import socket
from pathlib import Path
from urllib.parse import urlparse

from processor import process_portfolio_url
from utils.investor import extract_investor_name

logger = logging.getLogger(__name__)

MAX_URL_LENGTH = 2048

INPUT_FILE = Path("input_urls.csv")
OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "output.csv"

OUTPUT_FIELDS = [
    "source_url",
    "investor_name",
    "investor_website",
    "company_name",
    "company_website",
    "article_1",
    "article_2",
    "article_3",
]

BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata.google.internal.",
}


def _is_safe_url(url: str) -> bool:
    """Reject URLs targeting private/internal networks (SSRF protection)."""
    if len(url) > MAX_URL_LENGTH:
        logger.warning("URL too long (%d chars), skipping: %s...", len(url), url[:80])
        return False

    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    if hostname in BLOCKED_HOSTS:
        logger.warning("Blocked metadata host: %s", hostname)
        return False

    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
    except socket.gaierror:
        logger.warning("DNS resolution failed for: %s", hostname)
        return False

    for _, _, _, _, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            logger.warning("URL resolves to non-public IP %s: %s", ip, url)
            return False

    return True


def _derive_investor_website(source_url: str) -> str:
    """Extract base domain from portfolio URL as investor website."""
    try:
        parsed = urlparse(source_url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except ValueError:
        return ""


def load_processed_urls(output_file: Path) -> set[str]:
    """Load already-processed source URLs for resume support."""
    if not output_file.exists():
        return set()
    with open(output_file, newline="", encoding="utf-8") as f:
        return {
            row["source_url"].strip()
            for row in csv.DictReader(f)
            if (row.get("source_url") or "").strip()
        }


def run_pipeline() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"{INPUT_FILE} not found")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # 1. Read and validate input URLs
    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        raw_urls = [
            row[0].strip()
            for row in reader
            if row and row[0].strip().startswith("http")
        ]

    input_urls = []
    for url in raw_urls:
        if _is_safe_url(url):
            input_urls.append(url)
        else:
            logger.warning("Skipping unsafe URL: %s", url)

    if not input_urls:
        print("No valid URLs found in input file")
        return

    # 2. Resume logic
    processed_urls = load_processed_urls(OUTPUT_FILE)
    urls_to_process = [u for u in input_urls if u not in processed_urls]

    print(f"URLs in input file : {len(input_urls)}")
    print(f"Already processed  : {len(processed_urls)}")
    print(f"URLs to process now: {len(urls_to_process)}")

    if not urls_to_process:
        print("Nothing to process.")
        return

    # 3. Process each portfolio URL
    file_exists = OUTPUT_FILE.exists()

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        if not file_exists:
            writer.writeheader()

        for source_url in urls_to_process:
            investor_name = extract_investor_name(source_url)
            investor_website = _derive_investor_website(source_url)

            print(f"\nProcessing : {source_url}")
            print(f"Investor   : {investor_name}")
            print(f"Website    : {investor_website}")

            try:
                process_portfolio_url(
                    source_url=source_url,
                    investor_name=investor_name,
                    investor_website=investor_website,
                    csv_writer=writer,
                )
            except Exception as e:
                print(f"Pipeline failure for {source_url}: {e}")

    print(f"\nDone. Output written to {OUTPUT_FILE}")


if __name__ == "__main__":
    run_pipeline()
