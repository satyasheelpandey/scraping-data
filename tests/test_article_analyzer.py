# tests/test_article_analyzer.py
"""Tests for article_analyzer.py — deal information extraction via crawl4ai."""
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from article_analyzer import (
    fetch_article_content,
    _extract_text_from_html,
    _call_extraction_llm,
    _compute_population_ratio,
    analyze_deal,
)
from schema import DealInfo


class TestExtractTextFromHtml:
    """_extract_text_from_html extracts readable text from HTML/markdown."""

    def test_prefers_markdown_when_substantial(self) -> None:
        markdown = "This is a long markdown text " * 20
        html = "<html><body><p>HTML content</p></body></html>"
        result = _extract_text_from_html(html, markdown)
        assert "long markdown text" in result

    def test_falls_back_to_html_article_tag(self) -> None:
        html = """
        <html>
        <body>
            <nav>Navigation</nav>
            <article>
                <p>This is the main article content about the deal.
                It contains enough text to pass the 200 char threshold
                and should be extracted properly from the article tag.
                More content here to fill it up beyond the minimum length.</p>
            </article>
            <footer>Footer stuff</footer>
        </body>
        </html>
        """
        result = _extract_text_from_html(html, "")
        assert "main article content" in result
        assert "Navigation" not in result
        assert "Footer stuff" not in result

    def test_falls_back_to_body(self) -> None:
        html = """
        <html>
        <body>
            <div>Some body content that is long enough to be meaningful.
            We need at least some text here for the fallback to work properly.</div>
        </body>
        </html>
        """
        result = _extract_text_from_html(html, "")
        assert "body content" in result

    def test_truncates_to_max_chars(self) -> None:
        long_text = "A" * 10000
        html = f"<html><body><article><p>{long_text}</p></article></body></html>"
        result = _extract_text_from_html(html, "")
        assert len(result) <= 8000

    def test_strips_script_and_style_tags(self) -> None:
        html = """
        <html>
        <body>
            <script>var x = 1;</script>
            <style>.foo { color: red; }</style>
            <article>
                <p>Clean article text that should be extracted properly.
                This text is the deal content we want to get at.
                Enough text here to pass the threshold for content detection.</p>
            </article>
        </body>
        </html>
        """
        result = _extract_text_from_html(html, "")
        assert "var x" not in result
        assert "color: red" not in result
        assert "Clean article text" in result

    def test_returns_empty_on_no_body(self) -> None:
        result = _extract_text_from_html("<html></html>", "")
        assert result == ""


class TestFetchArticleContent:
    """fetch_article_content uses crawl4ai to fetch article pages."""

    @patch("article_analyzer.asyncio.run")
    def test_returns_crawled_text(self, mock_run: MagicMock) -> None:
        mock_run.return_value = "Article content about the deal " * 10
        result = fetch_article_content("https://example.com/article")
        assert "Article content" in result
        mock_run.assert_called_once()

    @patch("article_analyzer.asyncio.run")
    def test_returns_empty_on_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = TimeoutError("page timeout")
        result = fetch_article_content("https://example.com/slow")
        assert result == ""

    @patch("article_analyzer.asyncio.run")
    def test_returns_empty_on_runtime_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = RuntimeError("navigation failed")
        result = fetch_article_content("https://example.com/fail")
        assert result == ""


class TestCallExtractionLlm:
    """_call_extraction_llm returns parsed JSON with deal fields."""

    @patch("article_analyzer._client")
    def test_returns_parsed_json(self, mock_client: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "announcement_date": "2024-03-15",
            "deal_type": "Acquisition",
            "deal_value": 50000000,
            "deal_value_text": "$50 million",
            "currency": "USD",
            "deal_stage": "completed",
            "strategic_rationale": "Expand market presence.",
        })
        mock_client.chat.completions.create.return_value = mock_response

        result = _call_extraction_llm(
            "Article about acquisition...", "Acme Corp", "Fund Capital"
        )
        assert result["deal_type"] == "Acquisition"
        assert result["deal_value"] == 50000000
        assert result["currency"] == "USD"

    @patch("article_analyzer._client")
    def test_passes_company_and_investor_in_prompt(self, mock_client: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "{}"
        mock_client.chat.completions.create.return_value = mock_response

        _call_extraction_llm("text", "WidgetCo", "Big Fund LP")

        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        assert "WidgetCo" in user_msg
        assert "Big Fund LP" in user_msg

    @patch("article_analyzer._client")
    def test_handles_malformed_json(self, mock_client: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json {{"
        mock_client.chat.completions.create.return_value = mock_response

        result = _call_extraction_llm("text", "Co", "Fund")
        assert result == {}

    @patch("article_analyzer._client")
    def test_handles_none_content(self, mock_client: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_response

        result = _call_extraction_llm("text", "Co", "Fund")
        assert result == {}


class TestComputePopulationRatio:
    """_compute_population_ratio counts non-null key fields."""

    def test_all_fields_populated(self) -> None:
        info = DealInfo(
            announcement_date="2024-01-01",
            deal_type="Acquisition",
            deal_value=100.0,
            currency="USD",
            deal_stage="completed",
            strategic_rationale="Growth strategy.",
        )
        assert _compute_population_ratio(info) == 1.0

    def test_no_fields_populated(self) -> None:
        info = DealInfo()
        assert _compute_population_ratio(info) == 0.0

    def test_half_fields_populated(self) -> None:
        info = DealInfo(
            announcement_date="2024-01-01",
            deal_type="Acquisition",
            deal_value=100.0,
        )
        assert _compute_population_ratio(info) == 0.5

    def test_one_field_populated(self) -> None:
        info = DealInfo(deal_type="Merger")
        ratio = _compute_population_ratio(info)
        assert abs(ratio - 1 / 6) < 0.01

    def test_non_key_fields_dont_count(self) -> None:
        info = DealInfo(
            deal_value_text="$50M",
            source_article_url="https://example.com",
        )
        assert _compute_population_ratio(info) == 0.0


class TestAnalyzeDeal:
    """analyze_deal cascades through articles and stops early."""

    @patch("article_analyzer._call_extraction_llm")
    @patch("article_analyzer.fetch_article_content")
    def test_stops_on_first_sufficient_article(
        self, mock_fetch: MagicMock, mock_llm: MagicMock
    ) -> None:
        mock_fetch.return_value = "A" * 300
        mock_llm.return_value = {
            "announcement_date": "2024-01-01",
            "deal_type": "Acquisition",
            "deal_value": 50000000,
            "currency": "USD",
            "deal_stage": "completed",
            "strategic_rationale": "Market expansion.",
        }

        result = analyze_deal(
            ["https://a.com/1", "https://a.com/2", "https://a.com/3"],
            "Acme Corp",
            "Fund Capital",
        )

        assert result.deal_type == "Entry-deal"  # "Acquisition" auto-mapped
        assert result.source_article_url == "https://a.com/1"
        assert mock_fetch.call_count == 1
        assert mock_llm.call_count == 1

    @patch("article_analyzer._call_extraction_llm")
    @patch("article_analyzer.fetch_article_content")
    def test_cascades_when_first_article_insufficient(
        self, mock_fetch: MagicMock, mock_llm: MagicMock
    ) -> None:
        mock_fetch.return_value = "A" * 300
        mock_llm.side_effect = [
            {"deal_type": "Acquisition"},  # 1/6 = 16% < 50%
            {
                "announcement_date": "2024-01-01",
                "deal_type": "Acquisition",
                "deal_value": 50000000,
                "currency": "USD",
                "deal_stage": "completed",
                "strategic_rationale": "Growth.",
            },  # 6/6 = 100%
        ]

        result = analyze_deal(
            ["https://a.com/1", "https://a.com/2"],
            "Acme Corp",
            "Fund Capital",
        )

        assert result.source_article_url == "https://a.com/2"
        assert mock_llm.call_count == 2

    @patch("article_analyzer._call_extraction_llm")
    @patch("article_analyzer.fetch_article_content")
    def test_returns_best_across_all_articles(
        self, mock_fetch: MagicMock, mock_llm: MagicMock
    ) -> None:
        mock_fetch.return_value = "A" * 300
        mock_llm.side_effect = [
            {"deal_type": "Acquisition"},  # 1/6
            {"deal_type": "Acquisition", "currency": "USD"},  # 2/6
        ]

        result = analyze_deal(
            ["https://a.com/1", "https://a.com/2"],
            "Acme Corp",
            "Fund Capital",
        )

        assert result.currency == "USD"
        assert result.source_article_url == "https://a.com/2"

    @patch("article_analyzer._call_extraction_llm")
    @patch("article_analyzer.fetch_article_content")
    def test_returns_empty_deal_info_when_all_fail(
        self, mock_fetch: MagicMock, mock_llm: MagicMock
    ) -> None:
        mock_fetch.return_value = ""  # empty = too short

        result = analyze_deal(
            ["https://a.com/1", "https://a.com/2"],
            "Acme Corp",
            "Fund Capital",
        )

        assert result.deal_type is None
        assert result.announcement_date is None

    @patch("article_analyzer._call_extraction_llm")
    @patch("article_analyzer.fetch_article_content")
    def test_skips_empty_urls(
        self, mock_fetch: MagicMock, mock_llm: MagicMock
    ) -> None:
        mock_fetch.return_value = "A" * 300
        mock_llm.return_value = {
            "deal_type": "Acquisition",
            "deal_value": 100,
            "currency": "USD",
            "deal_stage": "completed",
            "announcement_date": "2024-01-01",
            "strategic_rationale": "Test.",
        }

        result = analyze_deal(
            ["", "", "https://a.com/3"],
            "Acme Corp",
            "Fund Capital",
        )

        assert mock_fetch.call_count == 1
        assert result.deal_type == "Entry-deal"  # "Acquisition" auto-mapped

    @patch("article_analyzer._call_extraction_llm")
    @patch("article_analyzer.fetch_article_content")
    def test_skips_short_article_text(
        self, mock_fetch: MagicMock, mock_llm: MagicMock
    ) -> None:
        mock_fetch.side_effect = ["Short", "A" * 300]
        mock_llm.return_value = {
            "deal_type": "Merger",
            "deal_value": 200,
            "currency": "EUR",
            "deal_stage": "announced",
            "announcement_date": "2024-06-01",
            "strategic_rationale": "Synergies.",
        }

        result = analyze_deal(
            ["https://a.com/1", "https://a.com/2"],
            "Co",
            "Fund",
        )

        assert mock_llm.call_count == 1
        assert result.deal_type == "Merger"
        assert result.source_article_url == "https://a.com/2"

    def test_handles_empty_article_list(self) -> None:
        result = analyze_deal([], "Co", "Fund")
        assert result.deal_type is None

    @patch("article_analyzer._call_extraction_llm")
    @patch("article_analyzer.fetch_article_content")
    def test_coerces_deal_value_to_float(
        self, mock_fetch: MagicMock, mock_llm: MagicMock
    ) -> None:
        mock_fetch.return_value = "A" * 300
        mock_llm.return_value = {
            "deal_type": "Acquisition",
            "deal_value": "50000000",  # string from LLM
            "currency": "USD",
            "deal_stage": "completed",
            "announcement_date": "2024-01-01",
            "strategic_rationale": "Growth.",
        }

        result = analyze_deal(
            ["https://a.com/1"], "Co", "Fund"
        )

        assert isinstance(result.deal_value, float)
        assert result.deal_value == 50000000.0
