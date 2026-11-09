# Imp News App 🗞️

A clean, responsive news web application built with **Python Flask** and **Tailwind CSS**. It delivers real-time news feeds by integrating with **NewsData.io** (for regional/Tamil news) and **Event Registry / GNews** (for English, Tech, Mysterious Tech, and Breaking News), backed by an **SQL Database for Saved Posts**, a **Google Gemini AI News Copilot**, an **automatic cross-API failover engine**, and a **Token-Saver in-memory cache**.

---

## 🚀 Key Features

* **Python Flask Backend:** Lightweight, robust, and clean routing with Jinja2 template rendering.
* **💾 Save Post (SQL Database):**
  * Persistent SQL database using **SQLite** (`news.db`) created automatically on startup.
  * Save and bookmark any news article with one click from Home, Category, or Breaking feeds.
  * Dedicated **Saved Posts** reading list page at `/saved` with search filter and removal controls.
  * Dynamic bookmark counter badge in the top navigation bar.
* **✨ Ask Gemini AI Copilot:**
  * Interactive modal dialog available on every single news card.
  * **1. Summarize News:** Instant 3-bullet executive takeaways capturing What, Why, and What's Next.
  * **2. Simple English Simplifier:** Rewrites complex geopolitical, financial, or tech jargon into clear 5th-grade plain English for easy reading.
  * **3. Ask Doubts Q&A:** Ask any custom question or doubt about the news story; Gemini analyzes the article and gives immediate, contextual answers.
  * Copy-to-clipboard button and suggestion chips.
* **Dual External News APIs with Automatic Failover:**
  * **NewsData.io:** Real-time Tamil regional news (`language="ta"`).
  * **Event Registry:** Global English, Tech updates, and Mysterious Tech research with active API authentication.
  * **GNews:** Secondary supported provider.
  * **Resilient Failover:** Feeds seamlessly fall back without breaking the UI.
* **Token-Saver In-Memory Caching (60-Minute TTL):**
  * Results are cached for 60 minutes in memory.
  * Preserves your 2,000 daily API token quota.
* **Strict Category Quotas & Token Caps:**
  * **Tamil News:** Capped at **30** articles.
  * **English News:** Capped at **30** articles.
  * **Tech News:** Capped at **15** articles.
  * **Mysterious Tech News:** Capped at **15** articles.
  * **Breaking News:** Capped at **15** articles.
* **Home Page Feeds:** Exactly **3 featured articles per category** displayed with responsive Tailwind cards and direct category links.
* **Deep Category Views with Pagination:** Dedicated `/category/<category_name>` routes with page navigation controls.

---

## 📁 File Structure

```text
IMP News App/
├── app.py                  # Main Flask application with routing & API endpoints
├── database.py             # SQLite SQL database module for Saved Posts
├── gemini_service.py       # Google Gemini AI service (Summary, Simple English, Doubts)
├── news.db                 # SQLite database file (created automatically)
├── .env.example            # Template for environment variables and API keys
├── .env                    # Local environment configuration
├── requirements.txt        # Python package dependencies (flask, requests, python-dotenv)
├── test_app.py             # Automated unit & integration test suite (7 tests)
├── templates/
│   ├── index.html          # Home landing page with 3 items per section & hero banner
│   ├── category.html       # Paginated category view with quota badges
│   ├── saved.html          # Saved posts reading list from SQL database
│   ├── 404.html            # Custom 404 Not Found error template
│   └── 500.html            # Custom 500 Internal Server error template
└── README.md               # Documentation and setup guide
```

---

## 🛠️ Quick Start Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys in `.env`
Ensure your `.env` contains your API credentials:
```env
NEWSDATA_API_KEY=pub_a961caf4e39b43238c14d18c478d2d0a
EVENTREGISTRY_API_KEY=86251082-373a-4529-889d-a1bf11515216
GEMINI_API_KEY=your_gemini_api_key_here
CACHE_TTL_SECONDS=3600
PORT=5000
```

> **Where to get a free Gemini API Key:**
> Get your free API key at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) and paste it into `GEMINI_API_KEY` in your `.env`.

### 3. Run the Application
```bash
python app.py
```
Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

### 4. Run Automated Tests
```bash
python test_app.py
```
