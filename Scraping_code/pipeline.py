# pipeline.py
import csv
import ipaddress
import logging
import socket
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from processor import process_portfolio_url

logger = logging.getLogger(__name__)

MAX_URL_LENGTH = 2048

INPUT_FILE = Path("../input_urls.csv")
OUTPUT_DIR = Path("output")

OUTPUT_FIELDS = [
    "url",
    "investor",
    "investor_link",
    "company",
    "company_url",
    "company_status",
    "strategy",
    "article_1",
    "article_2",
    "article_3",
    "announcement_date",
    "deal_type",
    "deal_value",
    "deal_value_text",
    "currency",
    "deal_stage",
    "strategic_rationale",
    "source_article_url",
]

BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata.google.internal.",
}


def _field(row: dict, key: str) -> str:
    """Extract a stripped string field from a CSV row."""
    return (row.get(key) or "").strip()


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


def load_processed_keys(output_dir: Path) -> set[tuple[str, str, str]]:
    """Load already-processed (url, company_status, strategy) tuples from all output files."""
    keys: set[tuple[str, str, str]] = set()
    if not output_dir.exists():
        return keys
    for csv_file in output_dir.glob("output_*.csv"):
        with open(csv_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                url = _field(row, "url")
                if url:
                    keys.add((url, _field(row, "company_status"), _field(row, "strategy")))
    return keys


def run_pipeline() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"{INPUT_FILE} not found")

    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"output_{timestamp}.csv"

    # 1. Read and validate input rows via DictReader
    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        input_rows = []
        for row in csv.DictReader(f):
            url = _field(row, "url")
            if not url.startswith("http"):
                continue
            if _is_safe_url(url):
                input_rows.append(row)
            else:
                logger.warning("Skipping unsafe URL: %s", url)

    if not input_rows:
        print("No valid URLs found in input file")
        return

    # 2. Resume logic — track (url, company_status, strategy) tuples across all runs
    processed_keys = load_processed_keys(OUTPUT_DIR)
    rows_to_process = [
        row for row in input_rows
        if (_field(row, "url"), _field(row, "company_status"), _field(row, "strategy"))
        not in processed_keys
    ]

    print(f"Rows in input file : {len(input_rows)}")
    print(f"Already processed  : {len(processed_keys)}")
    print(f"Rows to process now: {len(rows_to_process)}")

    if not rows_to_process:
        print("Nothing to process.")
        return

    # 3. Process each portfolio URL — each run writes a new timestamped file
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()

        for row in rows_to_process:
            source_url = _field(row, "url")
            investor_name = _field(row, "investor_name")
            investor_link = _field(row, "investor_link")
            company_status = _field(row, "company_status")
            strategy = _field(row, "strategy")
            filter_type = _field(row, "filter_type")
            js_status_filter = _field(row, "js_status_filter")
            js_strategy_filter = _field(row, "js_strategy_filter")

            print(f"\nProcessing : {source_url}")
            print(f"Investor   : {investor_name}")
            print(f"Link       : {investor_link}")
            print(f"Status     : {company_status}")
            print(f"Strategy   : {strategy}")
            if filter_type == "js_click":
                print(f"JS Filter  : status={js_status_filter!r}, strategy={js_strategy_filter!r}")

            try:
                process_portfolio_url(
                    source_url=source_url,
                    investor_name=investor_name,
                    investor_link=investor_link,
                    company_status=company_status,
                    strategy=strategy,
                    js_status_filter=js_status_filter if filter_type == "js_click" else "",
                    js_strategy_filter=js_strategy_filter if filter_type == "js_click" else "",
                    csv_writer=writer,
                )
            except Exception as e:
                print(f"Pipeline failure for {source_url}: {e}")

    print(f"\nDone. Output written to {output_file}")


if __name__ == "__main__":
    run_pipeline()
