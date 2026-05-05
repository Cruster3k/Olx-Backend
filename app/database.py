import os
import sqlite3

from .locations import enrich_location, normalize_location

DB_PATH = os.getenv("DB_PATH", "olx_listings.db")

REQUIRED_COLUMNS = {
    "first_seen_at": "TEXT",
    "last_seen_at": "TEXT",
    "is_new": "INTEGER DEFAULT 0",
    "listing_status": "TEXT DEFAULT 'unknown'",
    "thumb": "TEXT",
    "created_display": "TEXT",
    "discount_pct": "REAL DEFAULT 0",
    "market_median": "REAL",
    "deal_label": "TEXT DEFAULT 'none'",
    "deal_score": "REAL DEFAULT 0",
    "is_opportunity": "INTEGER DEFAULT 0",
    "is_suspicious": "INTEGER DEFAULT 0",
    "availability_status": "TEXT DEFAULT 'unknown'",
    "availability_checked_at": "TEXT",
    "unavailable_at": "TEXT",
    "location_normalized": "TEXT",
    "latitude": "REAL",
    "longitude": "REAL",
    "region": "TEXT",
    "province": "TEXT",
}


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            price REAL,
            url TEXT NOT NULL,
            category TEXT,
            model TEXT,
            condition TEXT,
            city TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(listings)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    for column_name, column_type in REQUIRED_COLUMNS.items():
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE listings ADD COLUMN {column_name} {column_type}")

    cursor.execute("""
        UPDATE listings
        SET first_seen_at = COALESCE(first_seen_at, scanned_at, created_at)
        WHERE first_seen_at IS NULL OR first_seen_at = ''
    """)
    cursor.execute("""
        UPDATE listings
        SET last_seen_at = COALESCE(last_seen_at, scanned_at, first_seen_at, created_at)
        WHERE last_seen_at IS NULL OR last_seen_at = ''
    """)
    cursor.execute("""
        UPDATE listings
        SET listing_status = COALESCE(NULLIF(listing_status, ''), 'unknown')
        WHERE listing_status IS NULL OR listing_status = ''
    """)
    cursor.execute("""
        UPDATE listings
        SET availability_status = COALESCE(NULLIF(availability_status, ''), 'unknown')
        WHERE availability_status IS NULL OR availability_status = ''
    """)

    cursor.execute("""
        SELECT id, city
        FROM listings
        WHERE location_normalized IS NULL OR location_normalized = ''
           OR latitude IS NULL
           OR longitude IS NULL
           OR province IS NULL OR province = ''
           OR region IS NULL OR region = ''
    """)
    for row in cursor.fetchall():
        location = enrich_location(row["city"])
        cursor.execute(
            """
            UPDATE listings
            SET location_normalized = ?,
                latitude = COALESCE(latitude, ?),
                longitude = COALESCE(longitude, ?),
                region = COALESCE(NULLIF(region, ''), ?),
                province = COALESCE(NULLIF(province, ''), ?)
            WHERE id = ?
            """,
            (
                location["location_normalized"],
                location["latitude"],
                location["longitude"],
                location["region"],
                location["province"],
                row["id"],
            ),
        )

    conn.commit()
    conn.close()
