"""
MySQL storage module for watches, preferences, and seen listings.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import mysql.connector
from mysql.connector import Error

from normalization import Filters, Preferences


# Database configuration - modify these for your local MySQL setup
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123",  # Set your MySQL root password here
    "database": "blocket_bot",
}


def get_connection():
    """Get a MySQL database connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        # If database doesn't exist, create it
        if "Unknown database" in str(e):
            create_database()
            return mysql.connector.connect(**DB_CONFIG)
        raise


def create_database():
    """Create the database if it doesn't exist."""
    config = DB_CONFIG.copy()
    del config["database"]
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
    conn.close()


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create watches table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watches (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255),
            query VARCHAR(255) NOT NULL,
            filters_json TEXT,
            preferences_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create seen_listings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seen_listings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            watch_id VARCHAR(36) NOT NULL,
            listing_id VARCHAR(255),
            url VARCHAR(1024) NOT NULL,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_watch_listing (watch_id, listing_id),
            UNIQUE KEY unique_watch_url (watch_id, url(255)),
            FOREIGN KEY (watch_id) REFERENCES watches(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# Initialize database on module load
try:
    init_db()
except Exception as e:
    print(f"Warning: Could not initialize database: {e}")
    print("Make sure MySQL is running and credentials are correct in storage.py")


def create_watch(
    name: Optional[str],
    query: str,
    filters: Optional[Filters] = None,
    preferences: Optional[Preferences] = None,
) -> str:
    """
    Create a new watch (saved search).

    Returns:
        The generated watch_id
    """
    watch_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()

    filters_json = json.dumps(filters.model_dump() if filters else {})
    preferences_json = json.dumps(preferences.model_dump() if preferences else {})

    cursor.execute(
        """
        INSERT INTO watches (id, name, query, filters_json, preferences_json)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (watch_id, name, query, filters_json, preferences_json),
    )

    conn.commit()
    conn.close()
    return watch_id


def get_watches() -> list[dict[str, Any]]:
    """Get all saved watches."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM watches ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    watches = []
    for row in rows:
        watches.append({
            "id": row["id"],
            "name": row["name"],
            "query": row["query"],
            "filters": json.loads(row["filters_json"]) if row["filters_json"] else {},
            "preferences": json.loads(row["preferences_json"]) if row["preferences_json"] else {},
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })

    return watches


def get_watch(watch_id: str) -> Optional[dict[str, Any]]:
    """Get a specific watch by ID."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM watches WHERE id = %s", (watch_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "query": row["query"],
        "filters": json.loads(row["filters_json"]) if row["filters_json"] else {},
        "preferences": json.loads(row["preferences_json"]) if row["preferences_json"] else {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def delete_watch(watch_id: str) -> bool:
    """Delete a watch by ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM watches WHERE id = %s", (watch_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()
    return deleted


def mark_listings_seen(watch_id: str, listings: list[dict[str, Any]]) -> int:
    """
    Mark listings as seen for a watch.

    Uses listing_id if available, otherwise falls back to URL for deduplication.

    Returns:
        Number of new listings marked
    """
    conn = get_connection()
    cursor = conn.cursor()
    new_count = 0

    for listing in listings:
        listing_id = listing.get("listing_id")
        url = listing.get("url", "")

        if not listing_id and not url:
            continue

        try:
            cursor.execute(
                """
                INSERT IGNORE INTO seen_listings (watch_id, listing_id, url)
                VALUES (%s, %s, %s)
                """,
                (watch_id, listing_id, url[:1024]),
            )
            if cursor.rowcount > 0:
                new_count += 1
        except Error:
            pass  # Ignore duplicate key errors

    conn.commit()
    conn.close()
    return new_count


def get_seen_listing_ids(watch_id: str) -> set[str]:
    """Get set of seen listing IDs for a watch."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT listing_id FROM seen_listings WHERE watch_id = %s AND listing_id IS NOT NULL",
        (watch_id,),
    )
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ids


def get_seen_urls(watch_id: str) -> set[str]:
    """Get set of seen URLs for a watch."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT url FROM seen_listings WHERE watch_id = %s",
        (watch_id,),
    )
    urls = {row[0] for row in cursor.fetchall()}
    conn.close()
    return urls


def filter_new_listings(watch_id: str, listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Filter listings to return only those not seen before.

    Uses listing_id if available, otherwise falls back to URL.
    """
    seen_ids = get_seen_listing_ids(watch_id)
    seen_urls = get_seen_urls(watch_id)

    new_listings = []
    for listing in listings:
        listing_id = listing.get("listing_id")
        url = listing.get("url", "")

        # Check if we've seen this listing before
        if listing_id and listing_id in seen_ids:
            continue
        if url and url in seen_urls:
            continue

        new_listings.append(listing)

    return new_listings


def update_watch(
    watch_id: str,
    name: Optional[str] = None,
    query: Optional[str] = None,
    filters: Optional[Filters] = None,
    preferences: Optional[Preferences] = None,
) -> bool:
    """Update an existing watch."""
    conn = get_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if name is not None:
        updates.append("name = %s")
        params.append(name)
    if query is not None:
        updates.append("query = %s")
        params.append(query)
    if filters is not None:
        updates.append("filters_json = %s")
        params.append(json.dumps(filters.model_dump()))
    if preferences is not None:
        updates.append("preferences_json = %s")
        params.append(json.dumps(preferences.model_dump()))

    if not updates:
        return False

    params.append(watch_id)
    cursor.execute(
        f"UPDATE watches SET {', '.join(updates)} WHERE id = %s",
        params,
    )

    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated
