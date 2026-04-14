# tests/test_scraper.py
"""Tests for scraper.py JS click filtering helpers."""
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from scraper import (
    _build_js_click_code,
    _build_js_code,
    crawl_portfolio_page,
)


class TestBuildJsClickCode:
    """_build_js_click_code generates correct JS for clicking filter elements."""

    def test_generates_js_with_filter_text(self) -> None:
        js = _build_js_click_code("Current")
        assert "'Current'" in js
        assert "el.click()" in js

    def test_escapes_single_quotes(self) -> None:
        js = _build_js_click_code("It's Active")
        assert "It\\'s Active" in js

    def test_escapes_backslashes(self) -> None:
        js = _build_js_click_code("Back\\slash")
        assert "Back\\\\slash" in js

    def test_matches_exact_or_startswith(self) -> None:
        js = _build_js_click_code("Realised")
        assert "=== 'Realised'" in js
        assert "startsWith('Realised')" in js


class TestBuildJsCode:
    """_build_js_code combines strategy and status click snippets."""

    def test_status_only(self) -> None:
        js = _build_js_code(js_status_filter="Current", js_strategy_filter="")
        assert "'Current'" in js
        # No delay needed when there's only one click
        assert "setTimeout" not in js

    def test_strategy_only(self) -> None:
        js = _build_js_code(js_status_filter="", js_strategy_filter="Mid Cap")
        assert "'Mid Cap'" in js

    def test_both_filters_strategy_first(self) -> None:
        js = _build_js_code(js_status_filter="Current", js_strategy_filter="Buyout")
        lines = js.split("\n")
        # Strategy click should come before status click
        strategy_idx = next(i for i, l in enumerate(lines) if "'Buyout'" in l)
        status_idx = next(i for i, l in enumerate(lines) if "'Current'" in l)
        assert strategy_idx < status_idx

    def test_delay_between_strategy_and_status(self) -> None:
        js = _build_js_code(js_status_filter="Current", js_strategy_filter="Buyout")
        assert "setTimeout" in js


class TestCrawlPortfolioPageJsParams:
    """crawl_portfolio_page accepts and forwards JS filter params."""

    @patch("scraper.asyncio.run")
    @patch("scraper._try_spa_data_endpoints", return_value=[])
    def test_accepts_js_filter_params(self, mock_spa, mock_run) -> None:
        mock_run.return_value = [("<html></html>", "# Page")]

        crawl_portfolio_page(
            "https://example.com/investments",
            js_status_filter="Current",
            js_strategy_filter="Mid Cap",
        )

        # asyncio.run should be called with _crawl coroutine including filters
        mock_run.assert_called_once()

    @patch("scraper.asyncio.run")
    @patch("scraper._try_spa_data_endpoints", return_value=[])
    def test_default_params_are_empty(self, mock_spa, mock_run) -> None:
        mock_run.return_value = [("<html></html>", "# Page")]

        crawl_portfolio_page("https://example.com/portfolio/")

        mock_run.assert_called_once()

    @patch("scraper.asyncio.run", side_effect=RuntimeError("test"))
    def test_returns_empty_on_error_with_filters(self, mock_run) -> None:
        result = crawl_portfolio_page(
            "https://example.com/investments",
            js_status_filter="Current",
        )
        assert result == ("", [], [], [], [])
