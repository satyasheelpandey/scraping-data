# db.py
import os
import logging

import psycopg2

logger = logging.getLogger(__name__)

DB_DSN = os.getenv("DATABASE_URL")

_schema_ready = False


def _get_conn():
    if not DB_DSN:
        return None
    return psycopg2.connect(DB_DSN)


def _ensure_schema_and_table(cur) -> None:
    global _schema_ready
    if _schema_ready:
        return
    cur.execute("CREATE SCHEMA IF NOT EXISTS source_db;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS source_db.investor_portfolio (
            id SERIAL PRIMARY KEY,
            url TEXT,
            investor TEXT,
            investor_link TEXT,
            company TEXT,
            company_url TEXT,
            company_status TEXT,
            strategy TEXT,
            article_1 TEXT,
            article_2 TEXT,
            article_3 TEXT,
            announcement_date TEXT,
            deal_type TEXT,
            deal_value DOUBLE PRECISION,
            deal_value_text TEXT,
            currency TEXT,
            deal_stage TEXT,
            strategic_rationale TEXT,
            source_article_url TEXT,
            stake_percentage DOUBLE PRECISION,
            stake TEXT,
            financial_metrics_reference_year INTEGER,
            valuation_m DOUBLE PRECISION,
            enterprise_value_m DOUBLE PRECISION,
            equity_value_m DOUBLE PRECISION,
            annual_revenue_m DOUBLE PRECISION,
            ebitda_m DOUBLE PRECISION,
            ebit_m DOUBLE PRECISION,
            operating_profit_m DOUBLE PRECISION,
            net_income_m DOUBLE PRECISION,
            net_profit_m DOUBLE PRECISION,
            revenue_multiple DOUBLE PRECISION,
            ebitda_multiple DOUBLE PRECISION,
            ebit_multiple DOUBLE PRECISION,
            ev_revenue_multiple DOUBLE PRECISION,
            ev_ebitda_multiple DOUBLE PRECISION,
            employee_count INTEGER,
            customer_count INTEGER,
            deal_structure TEXT,
            is_processed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT now()
        );
    """)
    _schema_ready = True


def insert_portfolio_row(record: dict) -> None:
    if not DB_DSN:
        logger.info("DATABASE_URL not set - skipping insert: %s", record.get("company"))
        return

    conn = None
    try:
        conn = _get_conn()
        with conn:
            with conn.cursor() as cur:
                _ensure_schema_and_table(cur)
                cur.execute(
                    """
                    INSERT INTO source_db.investor_portfolio
                        (url, investor, investor_link,
                         company, company_url,
                         company_status, strategy,
                         article_1, article_2, article_3,
                         announcement_date, deal_type, deal_value,
                         deal_value_text, currency, deal_stage,
                         strategic_rationale, source_article_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        record.get("url"),
                        record.get("investor"),
                        record.get("investor_link"),
                        record.get("company"),
                        record.get("company_url"),
                        record.get("company_status", ""),
                        record.get("strategy", ""),
                        record.get("article_1", ""),
                        record.get("article_2", ""),
                        record.get("article_3", ""),
                        record.get("announcement_date"),
                        record.get("deal_type"),
                        record.get("deal_value"),
                        record.get("deal_value_text"),
                        record.get("currency"),
                        record.get("deal_stage"),
                        record.get("strategic_rationale"),
                        record.get("source_article_url"),
                    ),
                )
        logger.info("Inserted: %s", record.get("company"))
    except psycopg2.Error as e:
        logger.error("DB insert failed: %s", e)
    finally:
        if conn:
            conn.close()
