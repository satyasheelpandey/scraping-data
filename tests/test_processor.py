# tests/test_processor.py
"""Tests for processor.py with 17-column record structure."""
import csv
import io
from unittest.mock import patch, MagicMock

import pytest

from processor import process_portfolio_url
from schema import DealInfo

FIELDNAMES_18 = [
    "url", "investor", "investor_link", "company", "company_url",
    "company_status", "strategy", "article_1", "article_2", "article_3",
    "announcement_date", "deal_type", "deal_value", "deal_value_text",
    "currency", "deal_stage", "strategic_rationale", "source_article_url",
]


class TestProcessorNewParams:
    """process_portfolio_url accepts company_status, strategy, investor_link."""

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="")
    @patch("processor.find_deal_articles", return_value={"articles": []})
    @patch("processor.analyze_deal", return_value=DealInfo())
    def test_accepts_company_status_param(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        mock_crawl.return_value = ("", [], [], [], [])
        mock_llm.return_value = []

        # Should not raise TypeError
        process_portfolio_url(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            investor_link="https://example.com",
            company_status="current",
            strategy="growth",
            csv_writer=None,
        )

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="https://acme.com")
    @patch("processor.find_deal_articles", return_value={"articles": [{"url": "https://deal.com/1", "score": 5}]})
    @patch("processor.analyze_deal")
    def test_record_uses_new_field_names(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        from schema import CompanySeed

        mock_crawl.return_value = ("", [], [], [], [])
        seed = CompanySeed(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            company_name="Acme Corp",
            company_website="",
        )
        mock_llm.return_value = [seed]
        mock_analyze.return_value = DealInfo(
            deal_type="Acquisition",
            currency="USD",
        )

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=FIELDNAMES_18)
        writer.writeheader()

        process_portfolio_url(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            investor_link="https://example.com",
            company_status="current",
            strategy="growth",
            csv_writer=writer,
        )

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)
        assert len(rows) == 1
        row = rows[0]

        # Core fields
        assert row["url"] == "https://example.com/portfolio/"
        assert row["investor"] == "Test Fund"
        assert row["investor_link"] == "https://example.com"
        assert row["company"] == "Acme Corp"
        assert row["company_url"] == "https://acme.com"
        assert row["company_status"] == "current"
        assert row["strategy"] == "growth"
        assert row["article_1"] == "https://deal.com/1"

        # Deal info fields
        assert row["deal_type"] == "Acquisition"
        assert row["currency"] == "USD"

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="")
    @patch("processor.find_deal_articles", return_value={"articles": []})
    @patch("processor.analyze_deal", return_value=DealInfo())
    def test_record_no_old_field_names(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        from schema import CompanySeed

        mock_crawl.return_value = ("", [], [], [], [])
        seed = CompanySeed(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            company_name="Acme Corp",
        )
        mock_llm.return_value = [seed]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=FIELDNAMES_18)
        writer.writeheader()

        process_portfolio_url(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            investor_link="https://example.com",
            company_status="current",
            strategy="growth",
            csv_writer=writer,
        )

        output.seek(0)
        rows = list(csv.DictReader(output))
        assert len(rows) == 1
        record = rows[0]
        # Old field names must NOT be present
        assert "source_url" not in record
        assert "investor_name" not in record
        assert "investor_website" not in record
        assert "company_name" not in record
        assert "company_website" not in record
        # New field names must be present
        assert "url" in record
        assert "investor" in record
        assert "investor_link" in record
        assert "company" in record
        assert "company_url" in record
        assert "company_status" in record
        assert "strategy" in record
        # Deal info fields must be present
        assert "announcement_date" in record
        assert "deal_type" in record
        assert "deal_value" in record
        assert "deal_value_text" in record
        assert "currency" in record
        assert "deal_stage" in record
        assert "strategic_rationale" in record
        assert "source_article_url" in record

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="https://acme.com")
    @patch("processor.find_deal_articles", return_value={"articles": [{"url": "https://deal.com/1", "score": 80}]})
    @patch("processor.analyze_deal")
    def test_record_has_18_columns(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        from schema import CompanySeed

        mock_crawl.return_value = ("", [], [], [], [])
        seed = CompanySeed(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            company_name="Acme Corp",
        )
        mock_llm.return_value = [seed]
        mock_analyze.return_value = DealInfo(
            announcement_date="2024-01-15",
            deal_type="Acquisition",
            deal_value=50000000.0,
            deal_value_text="$50 million",
            currency="USD",
            deal_stage="completed",
            strategic_rationale="Market expansion into EU.",
        )

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=FIELDNAMES_18)
        writer.writeheader()

        process_portfolio_url(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            investor_link="https://example.com",
            company_status="current",
            strategy="growth",
            csv_writer=writer,
        )

        output.seek(0)
        rows = list(csv.DictReader(output))
        assert len(rows) == 1
        row = rows[0]
        assert len(row) == 18
        assert row["announcement_date"] == "2024-01-15"
        assert row["deal_type"] == "Acquisition"
        assert row["deal_value"] == "50000000.0"
        assert row["deal_value_text"] == "$50 million"
        assert row["currency"] == "USD"
        assert row["deal_stage"] == "completed"
        assert row["strategic_rationale"] == "Market expansion into EU."

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="")
    @patch("processor.find_deal_articles", return_value={"articles": []})
    @patch("processor.analyze_deal", return_value=DealInfo())
    def test_analyze_deal_not_called_without_articles(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        from schema import CompanySeed

        mock_crawl.return_value = ("", [], [], [], [])
        seed = CompanySeed(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            company_name="Acme Corp",
        )
        mock_llm.return_value = [seed]

        process_portfolio_url(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            investor_link="https://example.com",
            csv_writer=None,
        )

        mock_analyze.assert_not_called()

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="")
    @patch("processor.find_deal_articles", return_value={"articles": [{"url": "https://deal.com/1", "score": 80}]})
    @patch("processor.analyze_deal")
    def test_analyze_deal_called_with_articles(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        from schema import CompanySeed

        mock_crawl.return_value = ("", [], [], [], [])
        seed = CompanySeed(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            company_name="Acme Corp",
        )
        mock_llm.return_value = [seed]
        mock_analyze.return_value = DealInfo()

        process_portfolio_url(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            investor_link="https://example.com",
            csv_writer=None,
        )

        mock_analyze.assert_called_once_with(
            article_urls=["https://deal.com/1", "", ""],
            company_name="Acme Corp",
            investor_name="Test Fund",
        )

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="")
    @patch("processor.find_deal_articles", return_value={"articles": [{"url": "https://deal.com/1", "score": 80}]})
    @patch("processor.analyze_deal", side_effect=Exception("LLM error"))
    def test_analyze_deal_error_does_not_crash(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        from schema import CompanySeed

        mock_crawl.return_value = ("", [], [], [], [])
        seed = CompanySeed(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            company_name="Acme Corp",
        )
        mock_llm.return_value = [seed]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=FIELDNAMES_18)
        writer.writeheader()

        # Should not raise
        result = process_portfolio_url(
            source_url="https://example.com/portfolio/",
            investor_name="Test Fund",
            investor_link="https://example.com",
            csv_writer=writer,
        )

        assert result is True
        output.seek(0)
        rows = list(csv.DictReader(output))
        assert len(rows) == 1
        # Deal fields should be empty strings on error
        assert rows[0]["deal_type"] == ""


class TestJsClickFilterPassthrough:
    """process_portfolio_url forwards JS click filters to crawl_portfolio_page."""

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="")
    @patch("processor.find_deal_articles", return_value={"articles": []})
    @patch("processor.analyze_deal", return_value=DealInfo())
    def test_forwards_js_status_filter(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        mock_crawl.return_value = ("", [], [], [], [])
        mock_llm.return_value = []

        process_portfolio_url(
            source_url="https://example.com/investments",
            investor_name="Equistone",
            investor_link="https://example.com",
            company_status="current",
            js_status_filter="Current",
            csv_writer=None,
        )

        mock_crawl.assert_called_once_with(
            "https://example.com/investments",
            js_status_filter="Current",
            js_strategy_filter="",
        )

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="")
    @patch("processor.find_deal_articles", return_value={"articles": []})
    @patch("processor.analyze_deal", return_value=DealInfo())
    def test_forwards_both_js_filters(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        mock_crawl.return_value = ("", [], [], [], [])
        mock_llm.return_value = []

        process_portfolio_url(
            source_url="https://example.com/investments",
            investor_name="IK Partners",
            investor_link="https://example.com",
            company_status="current",
            strategy="mid_cap",
            js_status_filter="Current",
            js_strategy_filter="Mid Cap",
            csv_writer=None,
        )

        mock_crawl.assert_called_once_with(
            "https://example.com/investments",
            js_status_filter="Current",
            js_strategy_filter="Mid Cap",
        )

    @patch("processor.crawl_portfolio_page")
    @patch("processor.extract_company_seeds")
    @patch("processor.find_official_company_website", return_value="")
    @patch("processor.find_deal_articles", return_value={"articles": []})
    @patch("processor.analyze_deal", return_value=DealInfo())
    def test_empty_filters_when_no_js_click(
        self, mock_analyze, mock_deals, mock_google, mock_llm, mock_crawl
    ) -> None:
        mock_crawl.return_value = ("", [], [], [], [])
        mock_llm.return_value = []

        process_portfolio_url(
            source_url="https://example.com/portfolio/",
            investor_name="Fund",
            investor_link="https://example.com",
            csv_writer=None,
        )

        mock_crawl.assert_called_once_with(
            "https://example.com/portfolio/",
            js_status_filter="",
            js_strategy_filter="",
        )
