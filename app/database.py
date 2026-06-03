import sqlite3
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/store_intelligence.db")

def get_db_connection():
    # If the URL has sqlite:///, extract path
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if db_path.startswith("sqlite://"):
        db_path = db_path.replace("sqlite://", "")
    
    # Check if a directory path exists, if so make it
    dir_name = os.path.dirname(db_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
        
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db_connection()
    try:
        # Create events table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            store_id TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            visitor_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            zone_id TEXT,
            dwell_ms INTEGER DEFAULT 0,
            is_staff INTEGER DEFAULT 0,
            confidence REAL DEFAULT 1.0,
            metadata_json TEXT,
            created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );
        """)
        
        # Create transactions table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            store_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            basket_value_inr REAL DEFAULT 0.0,
            item_count INTEGER DEFAULT 0,
            metadata_json TEXT
        );
        """)
        conn.commit()
    finally:
        conn.close()

def check_db_health() -> bool:
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1;").fetchone()
        conn.close()
        return True
    except Exception:
        return False
