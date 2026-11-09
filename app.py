"""
Imp News App - Main Flask Application (Token-Saver & Strict Quota Edition)

Key Optimizations:
1. Strict Quota Caps:
   - Tamil News: max 30 articles
   - English News: max 30 articles
   - Tech News: max 15 articles
   - Mysterious Tech News: max 15 articles
   - Breaking News: max 15 articles
2. In-Memory Caching (45-60 min TTL):
   - Cache results for 60 minutes (3600 seconds) to prevent burning API tokens on page visits/refreshes.
   - Shared cross-route cache: Home and Category pages share results so 0 extra tokens are wasted.
3. Batch Size & Rate-Limit Protection:
   - Request smaller, optimized batch sizes per API call.
   - Robust try/except blocks handling HTTP 429 Too Many Requests, quota exhaustion, and connectivity drops.
"""

import os
import math
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import requests
from flask import Flask, render_template, request, abort, jsonify
from dotenv import load_dotenv

# Load environment variables first before importing local modules
load_dotenv()

import database
import gemini_service

# -----------------------------------------------------------------------------
# 1. Environment & Initialization
# -----------------------------------------------------------------------------

# Initialize SQLite database for Saved Posts
database.init_db()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'imp-news-secret-key-2026')
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', '1') == '1'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# API Keys loaded securely from environment
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "").strip() or os.getenv("NEWS_API_KEY", "").strip()
EVENTREGISTRY_API_KEY = os.getenv("EVENTREGISTRY_API_KEY", "").strip()
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# If the user pasted an Event Registry UUID key into GNEWS_API_KEY, auto-assign it
if not EVENTREGISTRY_API_KEY and "-" in GNEWS_API_KEY:
    EVENTREGISTRY_API_KEY = GNEWS_API_KEY

# -----------------------------------------------------------------------------
# 2. Token-Saver Caching Configuration (45-60 Minutes TTL)
# -----------------------------------------------------------------------------
# 60 minutes = 3600 seconds. Prevents repeated external API requests from burning tokens.
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 3600))

# Shared in-memory cache dictionary:
# Structure: {cache_key: {"timestamp": float, "data": List[Dict]}}
_cache: Dict[str, Dict[str, Any]] = {}

# Text truncation limit (characters) to save payload tokens
MAX_DESC_CHARS = 140

# -----------------------------------------------------------------------------
# 3. Category Definitions & Strict Quotas
# -----------------------------------------------------------------------------
CATEGORIES: Dict[str, Dict[str, Any]] = {
    "tamil": {
        "slug": "tamil",
        "name": "Tamil News",
        "native_name": "தமிழ் செய்திகள் (General)",
        "description": "Stay informed with real-time news, cultural highlights, state policies, and current affairs from Tamil Nadu, India, and the Tamil diaspora.",
        "quota": 30,  # Reduced to maximum 30 articles to strictly conserve tokens
        "api_provider": "NewsData.io",
        "icon": "fa-language",
        "badge_class": "bg-rose-50 text-rose-700 border-rose-200 ring-rose-500/20"
    },
    "english": {
        "slug": "english",
        "name": "English News",
        "native_name": "Global & National Headlines",
        "description": "Comprehensive international reporting, national developments, geopolitical shifts, and frontline global affairs.",
        "quota": 30,  # Reduced to maximum 30 articles to strictly conserve tokens
        "api_provider": "Event Registry",
        "icon": "fa-globe",
        "badge_class": "bg-blue-50 text-blue-700 border-blue-200 ring-blue-500/20"
    },
    "tech": {
        "slug": "tech",
        "name": "Tech News & Updates",
        "native_name": "Innovation, AI & Gadgets",
        "description": "Deep-dives into artificial intelligence, emerging software platforms, semiconductors, consumer gadgets, and visionary tech startups.",
        "quota": 15,  # Capped at 15 articles to strictly conserve tokens
        "api_provider": "Event Registry",
        "icon": "fa-microchip",
        "badge_class": "bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-500/20"
    },
    "mysterious-tech": {
        "slug": "mysterious-tech",
        "name": "Mysterious Tech News",
        "native_name": "Enigmas, Quantum Anomalies & Fringe Tech",
        "description": "Exploring quantum paradoxes, unexplained electromagnetic phenomena, deep space communication signals, and classified technological frontiers.",
        "quota": 15,  # Capped at 15 articles to strictly conserve tokens
        "api_provider": "Event Registry",
        "icon": "fa-atom",
        "badge_class": "bg-purple-50 text-purple-700 border-purple-200 ring-purple-500/20"
    },
    "breaking": {
        "slug": "breaking",
        "name": "Breaking News",
        "native_name": "முக்கிய செய்திகள் / Urgent Alerts",
        "description": "Immediate, high-priority flash updates and developing headlines occurring right now across all spheres.",
        "quota": 15,  # Capped at 15 articles to strictly conserve tokens
        "api_provider": "Event Registry",
        "icon": "fa-bolt",
        "badge_class": "bg-red-50 text-red-700 border-red-200 ring-red-500/20"
    }
}

# -----------------------------------------------------------------------------
# Helper: Timestamp Formatter
# -----------------------------------------------------------------------------
def format_published_at(date_str: Optional[str]) -> str:
    """Safely format published date into friendly relative or calendar timestamp."""
    if not date_str:
        return "Recent"
    try:
        clean = date_str.replace("Z", "+00:00")
        if " " in clean and "+" not in clean:
            dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(clean)

        diff = datetime.now(timezone.utc) - dt
        seconds = diff.total_seconds()

        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        elif seconds < 604800:
            return f"{int(seconds // 86400)}d ago"
        else:
            return dt.strftime("%b %d, %Y")
    except Exception:
        return date_str[:16] if len(date_str) >= 10 else "Recent"


# -----------------------------------------------------------------------------
# 4. Optimized API Fetch Functions with In-Memory Caching & 429 Protection
# -----------------------------------------------------------------------------
def fetch_from_newsdata(language: str, query: str = "", category: str = "", size: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch live news from NewsData.io with:
    - In-memory cache check (60-minute TTL)
    - Controlled batch size (max 10)
    - Robust 429 (Rate Limit / Quota Exhaustion) handling
    """
    if not NEWSDATA_API_KEY:
        logger.warning("NEWSDATA_API_KEY not configured.")
        return []

    # Check In-Memory Cache first
    cache_key = f"newsdata_{language}_{query}_{category}_{size}"
    now = time.time()
    if cache_key in _cache:
        cached = _cache[cache_key]
        if now - cached["timestamp"] < CACHE_TTL_SECONDS:
            logger.info(f"[CACHE HIT] NewsData ({language}, q='{query}', cat='{category}') - 0 tokens used! (Cached for 60m)")
            return cached["data"]

    url = "https://newsdata.io/api/1/news"
    # Cap request size to 10 max per batch to preserve API credits
    batch_size = min(max(size, 1), 10)
    params = {
        "apikey": NEWSDATA_API_KEY,
        "language": language,
        "size": batch_size
    }
    if query:
        params["q"] = query
    if category:
        params["category"] = category

    try:
        logger.info(f"[API REQUEST] NewsData.io (language={language}, q='{query}', cat='{category}', size={batch_size})...")
        response = requests.get(url, params=params, timeout=10)

        # Handle 429 Rate Limit or Quota Exhaustion
        if response.status_code == 429:
            logger.warning("[RATE LIMIT 429] NewsData.io quota reached. Serving previously cached data if available.")
            if cache_key in _cache:
                return _cache[cache_key]["data"]
            return []

        if response.status_code == 200:
            data = response.json()
            raw_results = data.get("results", [])
            articles = []

            for idx, art in enumerate(raw_results[:batch_size]):
                source_id = art.get("source_id") or "NewsData"
                source_name = art.get("source_name") or source_id.capitalize()
                image = art.get("image_url") or "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?auto=format&fit=crop&w=800&q=80"

                raw_desc = art.get("description") or art.get("content") or "Click through to read full coverage."
                clean_desc = (raw_desc[:MAX_DESC_CHARS] + "...") if len(raw_desc) > MAX_DESC_CHARS else raw_desc

                articles.append({
                    "id": art.get("article_id") or f"nd-{idx}",
                    "title": art.get("title") or "Untitled News Story",
                    "description": clean_desc,
                    "content": art.get("content") or "",
                    "url": art.get("link") or "#",
                    "image": image,
                    "source": {"name": source_name},
                    "source_name": source_name,
                    "published_at": format_published_at(art.get("pubDate")),
                    "category_slug": "tamil" if language == "ta" else (category or "general"),
                    "category_name": "Tamil News" if language == "ta" else (category.capitalize() if category else "General News"),
                    "is_breaking": (idx == 0 or idx % 3 == 0),
                    "is_flash": (idx % 2 == 1)
                })

            if articles:
                # Save to in-memory cache with timestamp
                _cache[cache_key] = {"timestamp": now, "data": articles}
            return articles
        else:
            logger.warning(f"NewsData.io returned HTTP {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as exc:
        logger.error(f"Network exception connecting to NewsData.io: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error in fetch_from_newsdata: {exc}")

    # Fallback to stale cache on network failure
    if cache_key in _cache:
        return _cache[cache_key]["data"]
    return []


def fetch_from_eventregistry(query: str = "news", count: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch live news from Event Registry (eventregistry.org) with:
    - In-memory cache check (60-minute TTL) to preserve 2,000 tokens
    - Controlled count (max 10)
    - Robust 429/error handling
    """
    if not EVENTREGISTRY_API_KEY:
        return []

    clean_query = query.strip() if query and query.strip() else "news"
    batch_size = min(max(count, 1), 10)
    cache_key = f"eventreg_{clean_query}_{batch_size}"

    now = time.time()
    if cache_key in _cache:
        cached = _cache[cache_key]
        if now - cached["timestamp"] < CACHE_TTL_SECONDS:
            logger.info(f"[CACHE HIT] Event Registry (q='{clean_query}') - 0 tokens used! (Cached for 60m)")
            return cached["data"]

    url = "https://eventregistry.org/api/v1/article/getArticles"
    params = {
        "apiKey": EVENTREGISTRY_API_KEY,
        "resultType": "articles",
        "articlesCount": batch_size,
        "keyword": clean_query,
        "lang": "eng",
        "articlesSortBy": "date"
    }

    try:
        logger.info(f"[API REQUEST] Event Registry (q='{clean_query}', count={batch_size})...")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 429:
            logger.warning("[RATE LIMIT 429] Event Registry quota reached. Serving cache if available.")
            if cache_key in _cache:
                return _cache[cache_key]["data"]
            return []

        if response.status_code == 200:
            data = response.json()
            raw_articles = data.get("articles", {}).get("results", [])
            articles = []

            for idx, art in enumerate(raw_articles[:batch_size]):
                source_dict = art.get("source") or {}
                source_name = source_dict.get("title") or "Event Registry Verified"
                image = art.get("image") or "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80"

                raw_desc = art.get("body") or art.get("title") or "Click through to read full coverage."
                clean_desc = (raw_desc[:MAX_DESC_CHARS] + "...") if len(raw_desc) > MAX_DESC_CHARS else raw_desc

                articles.append({
                    "id": art.get("uri") or f"er-{idx}",
                    "title": art.get("title") or "Untitled Report",
                    "description": clean_desc,
                    "content": art.get("body") or "",
                    "url": art.get("url") or "#",
                    "image": image,
                    "source": {"name": source_name},
                    "source_name": source_name,
                    "published_at": format_published_at(art.get("dateTime") or art.get("date")),
                    "category_slug": clean_query,
                    "category_name": clean_query.capitalize(),
                    "is_breaking": (idx == 0 or idx % 3 == 0),
                    "is_flash": (idx % 2 == 1)
                })

            if articles:
                _cache[cache_key] = {"timestamp": now, "data": articles}
            return articles
        else:
            logger.warning(f"Event Registry returned HTTP {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as exc:
        logger.error(f"Network exception connecting to Event Registry: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error in fetch_from_eventregistry: {exc}")

    if cache_key in _cache:
        return _cache[cache_key]["data"]
    return []


def fetch_from_gnews(language: str, query: str = "news", max_articles: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch live news from GNews API with:
    - In-memory cache check (60-minute TTL)
    - Controlled batch size (max 5-10) to strictly conserve 2,000 tokens
    - Robust 429 Rate Limit / Quota handling
    """
    if not GNEWS_API_KEY:
        return []

    raw_key = GNEWS_API_KEY.strip()
    if "-" in raw_key:
        logger.warning(f"GNews key in .env contains hyphens (looks like an Account ID, not an API key). Using NewsData.io fallback.")
        return []

    clean_key = raw_key.replace("-", "").strip()

    # Pre-validation: GNews API keys must be exactly 32 hex chars
    if len(clean_key) != 32:
        return []

    search_query = query.strip() if query and query.strip() else "news"
    # Optimized batch limit to conserve tokens
    batch_limit = min(max(max_articles, 1), 10)
    cache_key = f"gnews_{language}_{search_query}_{batch_limit}"

    # Check In-Memory Cache first
    now = time.time()
    if cache_key in _cache:
        cached = _cache[cache_key]
        if now - cached["timestamp"] < CACHE_TTL_SECONDS:
            logger.info(f"[CACHE HIT] GNews ({language}, q='{search_query}') - 0 tokens used! (Cached for 60m)")
            return cached["data"]

    url = "https://gnews.io/api/v4/search"
    params = {
        "q": search_query,
        "lang": language,
        "max": batch_limit,
        "apikey": clean_key
    }

    try:
        logger.info(f"[API REQUEST] GNews API (q='{search_query}', max={batch_limit})...")
        response = requests.get(url, params=params, timeout=8)

        # Handle 429 Rate Limit or Quota Exhaustion
        if response.status_code == 429:
            logger.warning("[RATE LIMIT 429] GNews API quota reached. Serving previously cached data if available.")
            if cache_key in _cache:
                return _cache[cache_key]["data"]
            return []

        if response.status_code == 200:
            data = response.json()
            raw_articles = data.get("articles", [])
            articles = []

            for idx, art in enumerate(raw_articles[:batch_limit]):
                source_dict = art.get("source") or {}
                source_name = source_dict.get("name") or "GNews Verified"
                image = art.get("image") or "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80"

                raw_desc = art.get("description") or art.get("content") or "Click to read complete coverage."
                clean_desc = (raw_desc[:MAX_DESC_CHARS] + "...") if len(raw_desc) > MAX_DESC_CHARS else raw_desc

                articles.append({
                    "id": f"gnews-{idx}",
                    "title": art.get("title") or "Untitled Report",
                    "description": clean_desc,
                    "content": art.get("content") or "",
                    "url": art.get("url") or "#",
                    "image": image,
                    "source": {"name": source_name},
                    "source_name": source_name,
                    "published_at": format_published_at(art.get("publishedAt")),
                    "category_slug": search_query,
                    "category_name": search_query.capitalize(),
                    "is_breaking": (idx == 0 or idx % 3 == 0),
                    "is_flash": (idx % 2 == 1)
                })

            if articles:
                # Save to in-memory cache with timestamp
                _cache[cache_key] = {"timestamp": now, "data": articles}
            return articles
        else:
            logger.warning(f"GNews API returned HTTP {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as exc:
        logger.error(f"Network exception connecting to GNews: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error in fetch_from_gnews: {exc}")

    # Fallback to stale cache on network failure
    if cache_key in _cache:
        return _cache[cache_key]["data"]
    return []


# -----------------------------------------------------------------------------
# 5. Resilient Unified Category Fetcher (Dual API + Token Protection)
# -----------------------------------------------------------------------------
def get_articles_for_category(slug: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch articles adhering to the target category quotas:
    - Tamil: NewsData.io (capped at quota 30)
    - English: Event Registry primary -> GNews -> NewsData fallback (capped at quota 30)
    - Tech: Event Registry primary -> GNews -> NewsData fallback (capped at quota 15)
    - Mysterious Tech: Event Registry primary -> GNews -> NewsData fallback (capped at quota 15)
    - Breaking: Event Registry primary -> GNews -> NewsData fallback (capped at quota 15)
    """
    cat_meta = CATEGORIES.get(slug, {})
    max_quota = cat_meta.get("quota", limit)
    effective_limit = min(limit, max_quota)

    if slug == "tamil":
        return fetch_from_newsdata(language="ta", query="", size=effective_limit)

    elif slug == "english":
        articles = fetch_from_eventregistry(query="world news", count=effective_limit)
        if not articles:
            articles = fetch_from_gnews(language="en", query="news", max_articles=effective_limit)
        if not articles:
            articles = fetch_from_newsdata(language="en", query="", category="top", size=effective_limit)
        return articles[:max_quota]

    elif slug == "tech":
        articles = fetch_from_eventregistry(query="technology", count=effective_limit)
        if not articles:
            articles = fetch_from_gnews(language="en", query="technology", max_articles=effective_limit)
        if not articles:
            articles = fetch_from_newsdata(language="en", query="technology", category="technology", size=effective_limit)
        return articles[:max_quota]

    elif slug == "mysterious-tech":
        articles = fetch_from_eventregistry(query="quantum", count=effective_limit)
        if not articles:
            articles = fetch_from_gnews(language="en", query="science mystery", max_articles=effective_limit)
        if not articles:
            articles = fetch_from_newsdata(language="en", query="quantum OR science mystery OR universe", size=effective_limit)
        return articles[:max_quota]

    elif slug == "breaking":
        articles = fetch_from_eventregistry(query="breaking news", count=effective_limit)
        if not articles:
            articles = fetch_from_gnews(language="en", query="breaking flash news", max_articles=effective_limit)
        if not articles:
            articles = fetch_from_newsdata(language="en", category="top", size=effective_limit)
        return articles[:max_quota]

    return []


# -----------------------------------------------------------------------------
# URL Handlers & Context Processor
# -----------------------------------------------------------------------------
@app.url_defaults
def handle_category_url_param(endpoint, values):
    """Allow url_for to accept either 'category_name' or 'name' seamlessly."""
    if endpoint == 'category_view' and 'name' in values and 'category_name' not in values:
        values['category_name'] = values.pop('name')


@app.context_processor
def inject_global_data():
    """Make navigation categories, quota specs, cache status, and saved counts available globally."""
    has_newsdata = bool(NEWSDATA_API_KEY and NEWSDATA_API_KEY != "your_newsdata_api_key_here")
    has_eventreg = bool(EVENTREGISTRY_API_KEY and EVENTREGISTRY_API_KEY != "your_eventregistry_api_key_here")
    has_gnews = bool(GNEWS_API_KEY and GNEWS_API_KEY != "your_gnews_api_key_here")
    gemini_key = gemini_service.get_gemini_api_key()
    has_gemini = bool(gemini_key and gemini_key != "your_gemini_api_key_here")
    saved_count = database.get_saved_count()
    return {
        "categories": CATEGORIES,
        "current_year": datetime.now().year,
        "has_live_api": (has_newsdata or has_eventreg or has_gnews),
        "api_provider": "NewsData.io & Event Registry",
        "cache_minutes": CACHE_TTL_SECONDS // 60,
        "token_saver_active": True,
        "has_gemini": has_gemini,
        "saved_count": saved_count
    }


# -----------------------------------------------------------------------------
# 6. Routes Implementation
# -----------------------------------------------------------------------------
@app.route('/')
def home():
    """
    Home Route:
    - Displays exactly 3 featured articles per category on the home landing page.
    - Token-Saving Optimization: Derives breaking news from existing category results,
      completely eliminating a redundant 5th external API request on every home load!
    """
    # Request exactly 3 featured items per category
    tamil_articles = get_articles_for_category("tamil", limit=3)
    english_articles = get_articles_for_category("english", limit=3)
    tech_articles = get_articles_for_category("tech", limit=3)
    mysterious_tech_articles = get_articles_for_category("mysterious-tech", limit=3)

    # Token-Saver: Extract breaking articles from the already-fetched results
    breaking_articles: List[Dict[str, Any]] = []
    for cat_list in [english_articles, tech_articles, mysterious_tech_articles, tamil_articles]:
        for it in cat_list:
            if it.get("is_breaking") and len(breaking_articles) < 3:
                breaking_articles.append(it)

    if not breaking_articles and english_articles:
        breaking_articles = english_articles[:3]

    featured_feed: Dict[str, List[Dict[str, Any]]] = {
        "tamil": tamil_articles[:3],
        "english": english_articles[:3],
        "tech": tech_articles[:3],
        "mysterious-tech": mysterious_tech_articles[:3]
    }

    saved_ids, saved_urls = database.get_saved_ids_and_urls()

    return render_template(
        'index.html',
        featured_feed=featured_feed,
        breaking_news=breaking_articles,
        saved_ids=saved_ids,
        saved_urls=saved_urls
    )


@app.route('/category/<category_name>')
def category_view(category_name: str):
    """
    Category Route:
    - Enforces the user's strict quotas:
      * Tamil: max 30 articles
      * English: max 30 articles
      * Tech: max 15 articles
      * Mysterious Tech: max 15 articles
      * Breaking: max 15 articles
    - Serves cached data for 60 minutes to eliminate repeated API token deduction.
    """
    slug = category_name.lower().strip()
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    per_page = 6

    if slug not in CATEGORIES:
        abort(404)

    cat_meta = CATEGORIES[slug]
    target_quota = cat_meta["quota"]

    # Fetch live articles respecting the strict category quota
    raw_articles = get_articles_for_category(slug, limit=target_quota)

    # Enforce maximum quota ceiling
    capped_articles = raw_articles[:target_quota]

    total_items = len(capped_articles)
    total_pages = max(1, math.ceil(total_items / per_page)) if total_items > 0 else 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_items = capped_articles[start_idx:end_idx]

    saved_ids, saved_urls = database.get_saved_ids_and_urls()

    return render_template(
        'category.html',
        category_slug=slug,
        category_meta=cat_meta,
        articles=paginated_items,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
        per_page=per_page,
        saved_ids=saved_ids,
        saved_urls=saved_urls
    )


@app.route('/saved')
def saved_posts_view():
    """
    Saved Posts Route:
    - Displays all articles saved in the SQLite SQL database.
    - Full features: Search filter, Gemini AI tools, Read story, and Remove actions.
    """
    articles = database.get_all_saved_articles()
    saved_ids, saved_urls = database.get_saved_ids_and_urls()
    return render_template(
        'saved.html',
        articles=articles,
        total_saved=len(articles),
        saved_ids=saved_ids,
        saved_urls=saved_urls
    )


@app.route('/api/save-post', methods=['POST'])
def api_toggle_save():
    """
    API: Toggle Save Post in SQLite SQL Database.
    - If already saved, un-saves it.
    - If not saved, saves it.
    """
    data = request.get_json() or {}
    article_id = str(data.get("id") or data.get("article_id") or data.get("url") or "").strip()
    url = str(data.get("url") or "").strip()

    if not article_id and not url:
        return jsonify({"success": False, "error": "Missing article id or url"}), 400

    if database.is_article_saved(article_id=article_id, url=url):
        database.delete_saved_article(article_id=article_id, url=url)
        return jsonify({
            "success": True,
            "saved": False,
            "message": "Article removed from saved posts.",
            "saved_count": database.get_saved_count()
        })
    else:
        success = database.save_article(data)
        return jsonify({
            "success": success,
            "saved": True,
            "message": "Article saved to your library!",
            "saved_count": database.get_saved_count()
        })


@app.route('/api/unsave-post', methods=['POST'])
def api_unsave():
    """API: Explicitly remove an article from the SQL database."""
    data = request.get_json() or {}
    article_id = str(data.get("id") or data.get("article_id") or "").strip()
    url = str(data.get("url") or "").strip()

    removed = database.delete_saved_article(article_id=article_id, url=url)
    return jsonify({
        "success": removed,
        "saved_count": database.get_saved_count(),
        "message": "Article removed from saved posts."
    })


@app.route('/api/saved-posts', methods=['GET'])
def api_get_saved_status():
    """API: Return all saved article IDs and current total saved count."""
    saved_ids, saved_urls = database.get_saved_ids_and_urls()
    return jsonify({
        "success": True,
        "count": database.get_saved_count(),
        "saved_ids": list(saved_ids),
        "saved_urls": list(saved_urls)
    })


@app.route('/api/gemini/action', methods=['POST'])
def api_gemini_action():
    """
    API: Ask Gemini Assistant for News Stories.
    Actions supported:
    1. 'summary': 3-bullet point executive summary
    2. 'simple_english': Explains complex news in easy 5th-grade English
    3. 'ask_doubt': Directly answers user questions about the news
    """
    data = request.get_json() or {}
    action = data.get("action", "summary")
    title = data.get("title", "")
    description = data.get("description", "")
    content = data.get("content", "")
    question = data.get("question", "")

    if not title:
        return jsonify({"success": False, "error": "Article title is required."}), 400

    result = gemini_service.process_gemini_request(
        action=action,
        title=title,
        description=description,
        content=content,
        question=question
    )
    return jsonify(result)


@app.route('/api/health')
def health_check():
    """Diagnostic health check endpoint."""
    return jsonify({
        "status": "online",
        "app_name": "Imp News App",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token_saver_active": True,
        "cache_ttl_minutes": CACHE_TTL_SECONDS // 60,
        "categories": list(CATEGORIES.keys()),
        "category_quotas": {k: v["quota"] for k, v in CATEGORIES.items()},
        "cached_keys_count": len(_cache),
        "sql_database": "SQLite (news.db)",
        "saved_posts_count": database.get_saved_count(),
        "newsdata_api_configured": bool(NEWSDATA_API_KEY and NEWSDATA_API_KEY != "your_newsdata_api_key_here"),
        "eventregistry_api_configured": bool(EVENTREGISTRY_API_KEY and EVENTREGISTRY_API_KEY != "your_eventregistry_api_key_here"),
        "gnews_api_configured": bool(GNEWS_API_KEY and GNEWS_API_KEY != "your_gnews_api_key_here"),
        "gemini_api_configured": bool(gemini_service.get_gemini_api_key() and gemini_service.get_gemini_api_key() != "your_gemini_api_key_here")
    })


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


# -----------------------------------------------------------------------------
# Main Entrypoint
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '1') == '1'
    print(f"\n=======================================================")
    print(f"  * IMP NEWS APP - TOKEN SAVER & STRICT QUOTA ACTIVE")
    print(f"  * Quotas: Tamil={CATEGORIES['tamil']['quota']}, English={CATEGORIES['english']['quota']}, Tech={CATEGORIES['tech']['quota']}, Mysterious={CATEGORIES['mysterious-tech']['quota']}")
    print(f"  * In-Memory Cache TTL: {CACHE_TTL_SECONDS // 60} Minutes")
    print(f"  * Local URL: http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
