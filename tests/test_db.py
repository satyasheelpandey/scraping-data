# tests/test_db.py
"""Tests for db.py with source_db.investor_portfolio schema."""
from unittest.mock import patch, MagicMock

import pytest

import db


class TestEnsureSchemaAndTable:
    """Schema and table creation for source_db.investor_portfolio."""

    def test_creates_schema_and_table(self) -> None:
        mock_cursor = MagicMock()
        db._schema_ready = False

        db._ensure_schema_and_table(mock_cursor)

        calls = mock_cursor.execute.call_args_list
        assert len(calls) == 2

        # First call: create schema
        schema_sql = calls[0][0][0]
        assert "CREATE SCHEMA IF NOT EXISTS source_db" in schema_sql

        # Second call: create table
        table_sql = calls[1][0][0]
        assert "source_db.investor_portfolio" in table_sql
        assert "source_article_url TEXT" in table_sql
        assert "is_processed BOOLEAN DEFAULT FALSE" in table_sql

        db._schema_ready = False

    def test_table_has_all_18_data_columns_plus_is_processed(self) -> None:
        mock_cursor = MagicMock()
        db._schema_ready = False

        db._ensure_schema_and_table(mock_cursor)

        table_sql = mock_cursor.execute.call_args_list[1][0][0]
        for col in [
            "url ", "investor ", "investor_link ", "company ",
            "company_url ", "company_status ", "strategy ",
            "article_1 ", "article_2 ", "article_3 ",
            "announcement_date ", "deal_type ", "deal_value ",
            "deal_value_text ", "currency ", "deal_stage ",
            "strategic_rationale ", "source_article_url ",
            "is_processed ",
        ]:
            assert col in table_sql, f"Missing column: {col.strip()}"

        db._schema_ready = False

    def test_skips_when_already_created(self) -> None:
        mock_cursor = MagicMock()
        db._schema_ready = True

        db._ensure_schema_and_table(mock_cursor)

        mock_cursor.execute.assert_not_called()
        db._schema_ready = False


class TestInsertPortfolioRow:
    """INSERT targets source_db.investor_portfolio with all 18 columns."""

    @patch.object(db, "DB_DSN", "postgresql://test:test@localhost/test")
    @patch.object(db, "_get_conn")
    def test_insert_targets_correct_table(self, mock_get_conn: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        db._schema_ready = True  # skip schema creation

        record = {
            "url": "https://example.com/portfolio/",
            "investor": "Test Fund",
            "investor_link": "https://example.com",
            "company": "Acme Corp",
            "company_url": "https://acme.com",
            "company_status": "current",
            "strategy": "growth",
            "article_1": "https://deal1.com",
            "article_2": "",
            "article_3": "",
            "announcement_date": "2024-01-15",
            "deal_type": "Acquisition",
            "deal_value": 50000000.0,
            "deal_value_text": "$50 million",
            "currency": "USD",
            "deal_stage": "completed",
            "strategic_rationale": "Market expansion.",
            "source_article_url": "https://deal1.com",
        }
        db.insert_portfolio_row(record)

        insert_sql = mock_cursor.execute.call_args[0][0]
        insert_params = mock_cursor.execute.call_args[0][1]

        # Correct table
        assert "source_db.investor_portfolio" in insert_sql

        # All 18 columns in SQL
        assert "source_article_url" in insert_sql

        # Params include all values (18 params)
        assert len(insert_params) == 18
        assert "https://example.com/portfolio/" in insert_params
        assert "Test Fund" in insert_params
        assert "Acme Corp" in insert_params
        assert "https://deal1.com" in insert_params  # source_article_url

        db._schema_ready = False

    @patch.object(db, "DB_DSN", None)
    def test_skips_insert_when_no_dsn(self) -> None:
        db.insert_portfolio_row({"company": "Test"})
        # Should not raise
