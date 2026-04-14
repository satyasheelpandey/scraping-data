# tests/test_schema.py
"""Tests for CompanySeed and DealInfo schemas."""
from schema import CompanySeed, DealInfo


class TestCompanySeedNewFields:
    """CompanySeed must include company_status and strategy fields."""

    def test_company_status_field_exists(self) -> None:
        seed = CompanySeed(
            source_url="https://example.com/portfolio",
            investor_name="Test Fund",
            company_name="Acme Corp",
            company_status="current",
        )
        assert seed.company_status == "current"

    def test_strategy_field_exists(self) -> None:
        seed = CompanySeed(
            source_url="https://example.com/portfolio",
            investor_name="Test Fund",
            company_name="Acme Corp",
            strategy="growth",
        )
        assert seed.strategy == "growth"

    def test_company_status_defaults_to_empty(self) -> None:
        seed = CompanySeed(
            source_url="https://example.com/portfolio",
            investor_name="Test Fund",
            company_name="Acme Corp",
        )
        assert seed.company_status == ""

    def test_strategy_defaults_to_empty(self) -> None:
        seed = CompanySeed(
            source_url="https://example.com/portfolio",
            investor_name="Test Fund",
            company_name="Acme Corp",
        )
        assert seed.strategy == ""

    def test_all_fields_together(self) -> None:
        seed = CompanySeed(
            source_url="https://example.com/portfolio",
            investor_name="Test Fund",
            company_name="Acme Corp",
            company_website="https://acme.com",
            company_status="exited",
            strategy="buyout",
        )
        assert seed.source_url == "https://example.com/portfolio"
        assert seed.investor_name == "Test Fund"
        assert seed.company_name == "Acme Corp"
        assert seed.company_website == "https://acme.com"
        assert seed.company_status == "exited"
        assert seed.strategy == "buyout"


class TestDealInfo:
    """DealInfo model for extracted deal information."""

    def test_all_fields_default_to_none(self) -> None:
        info = DealInfo()
        assert info.announcement_date is None
        assert info.deal_type is None
        assert info.deal_value is None
        assert info.deal_value_text is None
        assert info.currency is None
        assert info.deal_stage is None
        assert info.strategic_rationale is None
        assert info.source_article_url is None

    def test_all_fields_populated(self) -> None:
        info = DealInfo(
            announcement_date="2024-03-15",
            deal_type="Acquisition",
            deal_value=50000000.0,
            deal_value_text="$50 million",
            currency="USD",
            deal_stage="completed",
            strategic_rationale="Expand market presence.",
            source_article_url="https://example.com/article",
        )
        assert info.announcement_date == "2024-03-15"
        assert info.deal_type == "Acquisition"
        assert info.deal_value == 50000000.0
        assert info.deal_value_text == "$50 million"
        assert info.currency == "USD"
        assert info.deal_stage == "completed"
        assert info.strategic_rationale == "Expand market presence."
        assert info.source_article_url == "https://example.com/article"

    def test_partial_fields(self) -> None:
        info = DealInfo(deal_type="Merger", currency="EUR")
        assert info.deal_type == "Merger"
        assert info.currency == "EUR"
        assert info.deal_value is None
        assert info.announcement_date is None

    def test_deal_value_accepts_float(self) -> None:
        info = DealInfo(deal_value=25000000.50)
        assert info.deal_value == 25000000.50

    def test_has_8_fields(self) -> None:
        assert len(DealInfo.model_fields) == 8
