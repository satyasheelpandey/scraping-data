# db.py
import os
import psycopg2
from psycopg2.extras import execute_values
import json

# Basic DB helper — adapt to your environment.
DB_DSN = os.getenv("POSTGRES_DSN")  # e.g. "postgresql://user:pass@host:5432/dbname"

def _get_conn():
    if not DB_DSN:
        # If DB not configured, fallback to print-only (safe)
        return None
    return psycopg2.connect(DB_DSN)

def insert_portfolio_row(record: dict):
    """
    Insert a single record into portfolio_companies table.
    Table schema (minimal): source_url, investor_name, company_name, company_website, keywords (jsonb)
    This function will try to create the table if it does not exist.
    If DB is not configured via POSTGRES_DSN, it will just print the record.
    """
    if not DB_DSN:
        print("[DB] POSTGRES_DSN not set — skipping DB insert. Record preview:", record)
        return

    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # ensure table exists
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS portfolio_companies (
                        id SERIAL PRIMARY KEY,
                        source_url TEXT,
                        investor_name TEXT,
                        company_name TEXT,
                        company_website TEXT,
                        keywords JSONB,
                        created_at TIMESTAMP DEFAULT now()
                    );
                    """
                )
                # insert
                cur.execute(
                    """
                    INSERT INTO portfolio_companies (source_url, investor_name, company_name, company_website, keywords)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        record.get("source_url"),
                        record.get("investor_name"),
                        record.get("company_name"),
                        record.get("company_website"),
                        json.dumps(record.get("keywords") or []),
                    ),
                )
        print("[DB] Inserted record:", record.get("company_name"))
    except Exception as e:
        print("[DB ERROR]", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
