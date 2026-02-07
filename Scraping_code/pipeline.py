# pipeline.py
import csv
import os

from processor import process_portfolio_url
from utils.investor import extract_investor_name

# Google deal finder
from deal_link_finder import find_ranked_deal_links


INPUT_FILE = "input_urls.csv"
OUTPUT_FILE = "output_portfolio.csv"
DEAL_LINK_FILE = "output_deal_links.csv"


# --------------------------------------------------
# LOAD ALREADY PROCESSED URLs (RESUME SUPPORT)
# --------------------------------------------------
def load_processed_urls(output_file: str) -> set[str]:
    processed = set()

    if not os.path.exists(output_file):
        return processed

    with open(output_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("source_url") or "").strip()
            if url:
                processed.add(url)

    return processed


# --------------------------------------------------
# MAIN PIPELINE
# --------------------------------------------------
def run_pipeline():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"{INPUT_FILE} not found")

    # --------------------------------------------------
    # 1️⃣ Read input URLs
    # --------------------------------------------------
    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        input_urls = [
            row[0].strip()
            for row in reader
            if row and row[0].strip().startswith("http")
        ]

    if not input_urls:
        print("❌ No valid URLs found in input file")
        return

    # --------------------------------------------------
    # 2️⃣ Resume logic
    # --------------------------------------------------
    processed_urls = load_processed_urls(OUTPUT_FILE)

    urls_to_process = [
        url for url in input_urls if url not in processed_urls
    ]

    print(f"⚙️ URLs in input file: {len(input_urls)}")
    print(f"⏩ Already processed: {len(processed_urls)}")
    print(f"🚀 URLs to process now: {len(urls_to_process)}")

    # --------------------------------------------------
    # 3️⃣ Portfolio scraping phase
    # --------------------------------------------------
    if urls_to_process:
        file_exists = os.path.exists(OUTPUT_FILE)

        with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
            fieldnames = [
                "source_url",
                "investor_name",
                "company_name",
                "company_website",
                "keywords",
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            for source_url in urls_to_process:
                investor_name = extract_investor_name(source_url)

                print(f"\n🔍 Processing: {source_url}")
                print(f"🏦 Investor: {investor_name}")

                try:
                    process_portfolio_url(
                        source_url=source_url,
                        investor_name=investor_name,
                        csv_writer=writer,
                    )
                except Exception as e:
                    print(f"❌ Pipeline failure for {source_url}: {e}")

    print("\n✅ Portfolio scraping phase completed.")

    # --------------------------------------------------
    # 4️⃣ DEAL / NEWS LINK DISCOVERY (ROBUST)
    # --------------------------------------------------
    print("\n🔗 Starting deal/news link discovery...")

    deal_file_exists = os.path.exists(DEAL_LINK_FILE)
    processed_sources = set()

    with open(OUTPUT_FILE, newline="", encoding="utf-8") as f_in, \
         open(DEAL_LINK_FILE, "a", newline="", encoding="utf-8") as f_out:

        reader = csv.DictReader(f_in)

        deal_fields = [
            "company_name",
            "investor_name",
            "deal_url",
            "score",
        ]

        writer = csv.DictWriter(f_out, fieldnames=deal_fields)

        if not deal_file_exists:
            writer.writeheader()

        for row in reader:
            source_url = (row.get("source_url") or "").strip()
            company = (row.get("company_name") or "").strip()
            investor = (row.get("investor_name") or "").strip()

            # ----------------------------------
            # CASE 1: Company-level deal search
            # ----------------------------------
            if company and investor:
                try:
                    results = find_ranked_deal_links(
                        target=company,
                        acquirer=investor,
                        top_k=3,
                    )

                    for r in results:
                        writer.writerow({
                            "company_name": company,
                            "investor_name": investor,
                            "deal_url": r["url"],
                            "score": r["score"],
                        })

                except Exception as e:
                    print(f"[DEAL LINK ERROR] {company}: {e}")

            # ----------------------------------
            # CASE 2: Investor-level fallback
            # ----------------------------------
            elif investor and source_url not in processed_sources:
                processed_sources.add(source_url)

                print(f"🔁 No companies found — investor-level deal search for {investor}")

                try:
                    results = find_ranked_deal_links(
                        target=investor,
                        acquirer=investor,
                        top_k=5,
                    )

                    for r in results:
                        writer.writerow({
                            "company_name": "",
                            "investor_name": investor,
                            "deal_url": r["url"],
                            "score": r["score"],
                        })

                except Exception as e:
                    print(f"[DEAL LINK ERROR] {investor}: {e}")

    print("🎯 Deal/news link discovery completed.")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------
if __name__ == "__main__":
    run_pipeline()
