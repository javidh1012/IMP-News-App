"""
database.py - SQLite SQL Database Module for Imp News App
Handles persistent storage for Saved Posts.
"""

import os
import sqlite3
import logging
from typing import List, Dict, Any, Tuple, Set

logger = logging.getLogger(__name__)

# Default database file path in project directory
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "news.db"))


def get_db_connection() -> sqlite3.Connection:
    """Create and return a SQLite database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQL schema for saved posts and relevant indexes."""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    content TEXT,
                    url TEXT NOT NULL,
                    image TEXT,
                    source_name TEXT,
                    published_at TEXT,
                    category_name TEXT,
                    category_slug TEXT,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_saved_posts_url ON saved_posts(url);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_saved_posts_article_id ON saved_posts(article_id);")
            conn.commit()
            logger.info(f"SQL Database initialized successfully at {DB_PATH}")
    except Exception as exc:
        logger.error(f"Failed to initialize SQL database: {exc}")
        raise


def save_article(article: Dict[str, Any]) -> bool:
    """Insert or update a saved article in the SQL database."""
    article_id = str(article.get("article_id") or article.get("id") or article.get("url", "")).strip()
    title = str(article.get("title", "")).strip()
    url = str(article.get("url", "")).strip()

    if not article_id or not title or not url:
        logger.warning("save_article: Missing mandatory fields (id, title, or url).")
        return False

    sql = """
        INSERT INTO saved_posts (
            article_id, title, description, content, url, image, 
            source_name, published_at, category_name, category_slug
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(article_id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            content = excluded.content,
            url = excluded.url,
            image = excluded.image,
            source_name = excluded.source_name,
            published_at = excluded.published_at,
            category_name = excluded.category_name,
            category_slug = excluded.category_slug,
            saved_at = CURRENT_TIMESTAMP;
    """
    params = (
        article_id,
        title,
        article.get("description", ""),
        article.get("content", ""),
        url,
        article.get("image", ""),
        article.get("source_name", "News Source"),
        article.get("published_at", "Recent"),
        article.get("category_name", "General"),
        article.get("category_slug", "general"),
    )

    try:
        with get_db_connection() as conn:
            conn.execute(sql, params)
            conn.commit()
            logger.info(f"Article saved to SQL database: '{title[:40]}' (ID: {article_id})")
            return True
    except Exception as exc:
        logger.error(f"Error saving article to SQL database: {exc}")
        return False


def delete_saved_article(article_id: str = None, url: str = None) -> bool:
    """Remove a saved article from the SQL database by article_id or URL."""
    if not article_id and not url:
        return False

    sql = "DELETE FROM saved_posts WHERE article_id = ? OR url = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(sql, (article_id or "", url or ""))
            conn.commit()
            logger.info(f"Removed article from SQL database. Rows affected: {cursor.rowcount}")
            return cursor.rowcount > 0
    except Exception as exc:
        logger.error(f"Error deleting saved article from SQL database: {exc}")
        return False


def is_article_saved(article_id: str = None, url: str = None) -> bool:
    """Check if an article is already saved in the database."""
    if not article_id and not url:
        return False

    sql = "SELECT 1 FROM saved_posts WHERE article_id = ? OR url = ? LIMIT 1;"
    try:
        with get_db_connection() as conn:
            row = conn.execute(sql, (article_id or "", url or "")).fetchone()
            return row is not None
    except Exception as exc:
        logger.error(f"Error checking saved status: {exc}")
        return False


def get_all_saved_articles() -> List[Dict[str, Any]]:
    """Retrieve all saved posts ordered by latest saved timestamp."""
    sql = """
        SELECT id, article_id, title, description, content, url, image,
               source_name, published_at, category_name, category_slug, saved_at
        FROM saved_posts
        ORDER BY saved_at DESC;
    """
    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.error(f"Error fetching saved articles: {exc}")
        return []


def get_saved_ids_and_urls() -> Tuple[Set[str], Set[str]]:
    """Return sets of saved article_ids and URLs for fast template checking."""
    sql = "SELECT article_id, url FROM saved_posts;"
    saved_ids: Set[str] = set()
    saved_urls: Set[str] = set()
    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
            for r in rows:
                if r["article_id"]:
                    saved_ids.add(r["article_id"])
                if r["url"]:
                    saved_urls.add(r["url"])
    except Exception as exc:
        logger.error(f"Error fetching saved IDs/URLs: {exc}")
    return saved_ids, saved_urls


def get_saved_count() -> int:
    """Return the total number of saved articles."""
    sql = "SELECT COUNT(*) AS cnt FROM saved_posts;"
    try:
        with get_db_connection() as conn:
            row = conn.execute(sql).fetchone()
            return row["cnt"] if row else 0
    except Exception as exc:
        logger.error(f"Error counting saved articles: {exc}")
        return 0


def clear_all_saved() -> bool:
    """Clear all saved posts from database."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM saved_posts;")
            conn.commit()
            return True
    except Exception as exc:
        logger.error(f"Error clearing saved posts: {exc}")
        return False

