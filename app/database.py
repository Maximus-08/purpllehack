import sqlite3
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/store_intelligence.db")

def get_db_connection():
    # If the URL is sqlite:////app/data/store_intelligence.db, extract path
    db_path = DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Setup tables
    pass
