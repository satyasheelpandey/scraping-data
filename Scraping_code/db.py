# db.py
import os
import logging

import psycopg2

logger = logging.getLogger(__name__)

DB_DSN = os.getenv("DATABASE_URL")

_table_created = False


def _get_conn():
    if not DB_DSN:
        return None
    return psycopg2.connect(DB_DSN)


def _ensure_table(cur) -> None:
    global _table_created
    if _table_created:
        return
    cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_companies (
            id SERIAL PRIMARY KEY,
            source_url TEXT,
            investor_name TEXT,
            investor_website TEXT,
            company_name TEXT,
            company_website TEXT,
            article_1 TEXT,
            article_2 TEXT,
            article_3 TEXT,
            created_at TIMESTAMP DEFAULT now()
        );
    """)
    _table_created = True


def insert_portfolio_row(record: dict) -> None:
    if not DB_DSN:
        logger.info("DATABASE_URL not set - skipping insert: %s", record.get("company_name"))
        return

    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    """
                    INSERT INTO portfolio_companies
                        (source_url, investor_name, investor_website,
                         company_name, company_website,
                         article_1, article_2, article_3)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        record.get("source_url"),
                        record.get("investor_name"),
                        record.get("investor_website"),
                        record.get("company_name"),
                        record.get("company_website"),
                        record.get("article_1", ""),
                        record.get("article_2", ""),
                        record.get("article_3", ""),
                    ),
                )
        logger.info("Inserted: %s", record.get("company_name"))
    except psycopg2.Error as e:
        logger.error("DB insert failed: %s", e)
    finally:
        if conn:
            conn.close()
