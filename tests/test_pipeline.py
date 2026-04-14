# tests/test_pipeline.py
"""Tests for pipeline.py with new CSV input/output structure."""
import csv
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import pipeline


class TestOutputFields:
    """OUTPUT_FIELDS must match the 18-column structure."""

    def test_output_fields_has_18_columns(self) -> None:
        assert len(pipeline.OUTPUT_FIELDS) == 18

    def test_output_fields_exact_names(self) -> None:
        expected = [
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
        assert pipeline.OUTPUT_FIELDS == expected


class TestInputFilePath:
    """INPUT_FILE must point to project root (../input_urls.csv from Scraping_code)."""

    def test_input_file_is_parent_dir(self) -> None:
        assert pipeline.INPUT_FILE == Path("../input_urls.csv")


class TestLoadProcessedKeys:
    """Resume logic tracks (url, company_status, strategy) tuples, not just URL."""

    def test_load_processed_returns_set_of_tuples(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_csv = output_dir / "output_20260101_000000.csv"
        output_csv.write_text(
            "url,investor,investor_link,company,company_url,"
            "company_status,strategy,article_1,article_2,article_3\n"
            "https://a.com/portfolio/,Fund A,https://a.com,Acme,https://acme.com,"
            "current,growth,,,\n"
            "https://a.com/portfolio/,Fund A,https://a.com,Beta,https://beta.com,"
            "exited,growth,,,\n",
            encoding="utf-8",
        )
        result = pipeline.load_processed_keys(output_dir)
        assert ("https://a.com/portfolio/", "current", "growth") in result
        assert ("https://a.com/portfolio/", "exited", "growth") in result

    def test_load_processed_returns_empty_set_for_missing_file(self, tmp_path: Path) -> None:
        result = pipeline.load_processed_keys(tmp_path / "nonexistent.csv")
        assert result == set()

    def test_same_url_different_status_are_distinct(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_csv = output_dir / "output_20260101_000000.csv"
        output_csv.write_text(
            "url,investor,investor_link,company,company_url,"
            "company_status,strategy,article_1,article_2,article_3\n"
            "https://x.com/p/,Fund,https://x.com,Co1,https://co1.com,current,buyout,,,\n",
            encoding="utf-8",
        )
        result = pipeline.load_processed_keys(output_dir)
        assert ("https://x.com/p/", "current", "buyout") in result
        assert ("https://x.com/p/", "exited", "buyout") not in result


class TestInputParsing:
    """Pipeline reads new rich CSV with DictReader and passes metadata through."""

    def test_reads_investor_name_from_csv(self, tmp_path: Path) -> None:
        input_csv = tmp_path / "input_urls.csv"
        input_csv.write_text(
            "url,investor_name,investor_link,company_status,strategy,"
            "filter_type,js_status_filter,js_strategy_filter,notes\n"
            "https://example.com/portfolio/,Test Fund,https://example.com,"
            "current,growth,none,,,Test notes\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"

        with patch.object(pipeline, "INPUT_FILE", input_csv), \
             patch.object(pipeline, "OUTPUT_DIR", output_dir), \
patch.object(pipeline, "_is_safe_url", return_value=True), \
             patch("pipeline.process_portfolio_url") as mock_process:
            pipeline.run_pipeline()

        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args
        # Should pass investor_name from CSV, not derived from URL
        assert call_kwargs[1]["investor_name"] == "Test Fund" or \
               call_kwargs.kwargs.get("investor_name") == "Test Fund"

    def test_passes_investor_link_to_processor(self, tmp_path: Path) -> None:
        input_csv = tmp_path / "input_urls.csv"
        input_csv.write_text(
            "url,investor_name,investor_link,company_status,strategy,"
            "filter_type,js_status_filter,js_strategy_filter,notes\n"
            "https://example.com/portfolio/,Test Fund,https://example.com,"
            "current,growth,none,,,\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"

        with patch.object(pipeline, "INPUT_FILE", input_csv), \
             patch.object(pipeline, "OUTPUT_DIR", output_dir), \
patch.object(pipeline, "_is_safe_url", return_value=True), \
             patch("pipeline.process_portfolio_url") as mock_process:
            pipeline.run_pipeline()

        call_kwargs = mock_process.call_args
        assert "investor_link" in (call_kwargs[1] if call_kwargs[1] else {}) or \
               "investor_link" in (call_kwargs.kwargs or {})

    def test_passes_company_status_to_processor(self, tmp_path: Path) -> None:
        input_csv = tmp_path / "input_urls.csv"
        input_csv.write_text(
            "url,investor_name,investor_link,company_status,strategy,"
            "filter_type,js_status_filter,js_strategy_filter,notes\n"
            "https://example.com/portfolio/,Fund,https://example.com,"
            "exited,buyout,none,,,\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"

        with patch.object(pipeline, "INPUT_FILE", input_csv), \
             patch.object(pipeline, "OUTPUT_DIR", output_dir), \
patch.object(pipeline, "_is_safe_url", return_value=True), \
             patch("pipeline.process_portfolio_url") as mock_process:
            pipeline.run_pipeline()

        call_kwargs = mock_process.call_args
        assert "company_status" in (call_kwargs[1] if call_kwargs[1] else {}) or \
               "company_status" in (call_kwargs.kwargs or {})

    def test_passes_strategy_to_processor(self, tmp_path: Path) -> None:
        input_csv = tmp_path / "input_urls.csv"
        input_csv.write_text(
            "url,investor_name,investor_link,company_status,strategy,"
            "filter_type,js_status_filter,js_strategy_filter,notes\n"
            "https://example.com/portfolio/,Fund,https://example.com,"
            "current,venture,none,,,\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"

        with patch.object(pipeline, "INPUT_FILE", input_csv), \
             patch.object(pipeline, "OUTPUT_DIR", output_dir), \
patch.object(pipeline, "_is_safe_url", return_value=True), \
             patch("pipeline.process_portfolio_url") as mock_process:
            pipeline.run_pipeline()

        call_kwargs = mock_process.call_args
        assert "strategy" in (call_kwargs[1] if call_kwargs[1] else {}) or \
               "strategy" in (call_kwargs.kwargs or {})


class TestJsClickFiltering:
    """Pipeline passes js_status_filter and js_strategy_filter for js_click rows."""

    def test_passes_js_filters_for_js_click_row(self, tmp_path: Path) -> None:
        input_csv = tmp_path / "input_urls.csv"
        input_csv.write_text(
            "url,investor_name,investor_link,company_status,strategy,"
            "filter_type,js_status_filter,js_strategy_filter,notes\n"
            "https://example.com/portfolio/,Fund,https://example.com,"
            "current,mid_cap,js_click,Current,Mid Cap,JS tabs\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"

        with patch.object(pipeline, "INPUT_FILE", input_csv), \
             patch.object(pipeline, "OUTPUT_DIR", output_dir), \
patch.object(pipeline, "_is_safe_url", return_value=True), \
             patch("pipeline.process_portfolio_url") as mock_process:
            pipeline.run_pipeline()

        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["js_status_filter"] == "Current"
        assert call_kwargs["js_strategy_filter"] == "Mid Cap"

    def test_does_not_pass_js_filters_for_url_param_row(self, tmp_path: Path) -> None:
        input_csv = tmp_path / "input_urls.csv"
        input_csv.write_text(
            "url,investor_name,investor_link,company_status,strategy,"
            "filter_type,js_status_filter,js_strategy_filter,notes\n"
            "https://example.com/portfolio/?status=current,Fund,https://example.com,"
            "current,growth,url_param,Current,,URL param\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"

        with patch.object(pipeline, "INPUT_FILE", input_csv), \
             patch.object(pipeline, "OUTPUT_DIR", output_dir), \
patch.object(pipeline, "_is_safe_url", return_value=True), \
             patch("pipeline.process_portfolio_url") as mock_process:
            pipeline.run_pipeline()

        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["js_status_filter"] == ""
        assert call_kwargs["js_strategy_filter"] == ""

    def test_does_not_pass_js_filters_for_none_filter_type(self, tmp_path: Path) -> None:
        input_csv = tmp_path / "input_urls.csv"
        input_csv.write_text(
            "url,investor_name,investor_link,company_status,strategy,"
            "filter_type,js_status_filter,js_strategy_filter,notes\n"
            "https://example.com/portfolio/,Fund,https://example.com,"
            "current,,none,,,Static HTML\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"

        with patch.object(pipeline, "INPUT_FILE", input_csv), \
             patch.object(pipeline, "OUTPUT_DIR", output_dir), \
patch.object(pipeline, "_is_safe_url", return_value=True), \
             patch("pipeline.process_portfolio_url") as mock_process:
            pipeline.run_pipeline()

        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["js_status_filter"] == ""
        assert call_kwargs["js_strategy_filter"] == ""


class TestNoInvestorImport:
    """Pipeline should NOT import extract_investor_name anymore."""

    def test_no_extract_investor_name_import(self) -> None:
        assert not hasattr(pipeline, "extract_investor_name")

    def test_no_derive_investor_website_function(self) -> None:
        assert not hasattr(pipeline, "_derive_investor_website")


class TestResumeWithTupleKeys:
    """Resume skips only matching (url, status, strategy) combos."""

    def test_skips_already_processed_combo(self, tmp_path: Path) -> None:
        input_csv = tmp_path / "input_urls.csv"
        input_csv.write_text(
            "url,investor_name,investor_link,company_status,strategy,"
            "filter_type,js_status_filter,js_strategy_filter,notes\n"
            "https://a.com/p/,Fund A,https://a.com,current,growth,none,,,\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_csv = output_dir / "output_20260101_000000.csv"
        output_csv.write_text(
            "url,investor,investor_link,company,company_url,"
            "company_status,strategy,article_1,article_2,article_3\n"
            "https://a.com/p/,Fund A,https://a.com,Acme,https://acme.com,"
            "current,growth,,,\n",
            encoding="utf-8",
        )

        with patch.object(pipeline, "INPUT_FILE", input_csv), \
             patch.object(pipeline, "OUTPUT_DIR", output_dir), \
             patch.object(pipeline, "_is_safe_url", return_value=True), \
             patch("pipeline.process_portfolio_url") as mock_process:
            pipeline.run_pipeline()

        mock_process.assert_not_called()

    def test_processes_same_url_different_status(self, tmp_path: Path) -> None:
        input_csv = tmp_path / "input_urls.csv"
        input_csv.write_text(
            "url,investor_name,investor_link,company_status,strategy,"
            "filter_type,js_status_filter,js_strategy_filter,notes\n"
            "https://a.com/p/,Fund A,https://a.com,exited,growth,none,,,\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_csv = output_dir / "output_20260101_000000.csv"
        # Only "current" was processed, "exited" should still run
        output_csv.write_text(
            "url,investor,investor_link,company,company_url,"
            "company_status,strategy,article_1,article_2,article_3\n"
            "https://a.com/p/,Fund A,https://a.com,Acme,https://acme.com,"
            "current,growth,,,\n",
            encoding="utf-8",
        )

        with patch.object(pipeline, "INPUT_FILE", input_csv), \
             patch.object(pipeline, "OUTPUT_DIR", output_dir), \
             patch.object(pipeline, "_is_safe_url", return_value=True), \
             patch("pipeline.process_portfolio_url") as mock_process:
            pipeline.run_pipeline()

        mock_process.assert_called_once()
