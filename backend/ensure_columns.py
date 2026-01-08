# ensure_columns.py
from sqlalchemy import text
from db_connection import engine

with engine.begin() as conn:
    conn.execute(text("ALTER TABLE courses ADD COLUMN IF NOT EXISTS prereq_text TEXT"))
    conn.execute(text("ALTER TABLE courses ADD COLUMN IF NOT EXISTS coreq_text TEXT"))

print("✅ Columns ensured successfully.")
