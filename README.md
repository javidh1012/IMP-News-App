# Imp News App 🗞️

A modern, responsive news web application built with **Python Flask**, **Tailwind CSS**, and **SQLite**. Powered by dual news APIs (**NewsData.io** & **Event Registry**) with an automatic failover engine, token-saving in-memory cache, and an integrated **Google Gemini AI News Copilot**.

---

### 🌐 Live Demo
Experience the live application deployed on **Render**:  
👉 **[https://imp-news-app.onrender.com/](https://imp-news-app.onrender.com/)**

[![Render Status](https://img.shields.io/badge/Deployed%20on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://imp-news-app.onrender.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-black?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-AI%20Copilot-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)](https://aistudio.google.com/)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-Responsive%20UI-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)

---

## 🚀 Key Features

* **🌐 Live Production Deployment:** Hosted as a high-performance web service on [Render](https://imp-news-app.onrender.com/) powered by **Gunicorn** WSGI.
* **💾 Save Post (Persistent SQLite Database):**
  * Persistent SQL database (`news.db`) created automatically on startup.
  * 1-click bookmark/unbookmark toggle directly on every news card across all categories.
  * Dedicated **Saved Articles** reading list at [`/saved`](https://imp-news-app.onrender.com/saved) with live search filter and removal controls.
  * Real-time bookmark counter badge in the navigation bar.
* **🤖 Google Gemini AI News Copilot:**
  * Integrated modal assistant directly accessible on each news post.
  * **1. Instant 3-Bullet Summary:** Concise takeaways covering what happened, why it matters, and next steps.
  * **2. Simple English Mode:** Translates complex geopolitical, technical, or financial jargon into plain 5th-grade language.
  * **3. Ask Doubts Q&A:** Ask questions or clarify details about any article with direct contextual answers.
  * Auto-fallback across current Gemini models (`gemini-3.5-flash-lite`, `gemini-flash-lite-latest`, `gemini-3.5-flash`, `gemini-3.8-flash`).
* **🛡️ Dual News APIs with Automatic Failover:**
  * **NewsData.io:** Real-time regional Tamil news feed (`language="ta"`).
  * **Event Registry:** Deep global news, tech innovation, and mysterious tech feeds.
  * **GNews:** Secondary fallback provider.
  * Seamless failover logic ensures feeds never show empty error screens.
* **⚡ Token-Saver In-Memory Cache (60-Min TTL):**
  * Shared in-memory caching layer stores fetched results for 60 minutes (3600s).
  * Conserves daily external API quota and ensures instant sub-second page loads.
* **📊 Strict Category Display Quotas:**
  * **Tamil News:** Capped at **30** articles.
  * **English News:** Capped at **30** articles.
  * **Tech News:** Capped at **15** articles.
  * **Mysterious Tech News:** Capped at **15** articles.
  * **Breaking News:** Capped at **15** articles.

---

## 📁 Project Structure

```text
IMP News App/
├── app.py                  # Main Flask application, routes & API endpoints
├── database.py             # SQLite SQL database module for Saved Posts
├── gemini_service.py       # Google Gemini AI integration (Summary, Simple English, Doubts)
├── news.db                 # SQLite database file (generated automatically)
├── .env.example            # Environment variables template
├── .env                    # Local environment secrets (ignored by Git)
├── requirements.txt        # Production Python dependencies (Flask, Gunicorn, requests, etc.)
├── test_app.py             # Automated test suite (7 comprehensive test cases)
├── templates/
│   ├── index.html          # Home feed with category previews & hero section
│   ├── category.html       # Paginated category view with quota indicators
│   ├── saved.html          # Saved posts reading list from SQL database
│   ├── 404.html            # Custom 404 error page
│   └── 500.html            # Custom 500 error page
└── README.md               # Project documentation & deployment guide
```

---

## ☁️ Deployment on Render

This project is optimized for deployment on **Render**:

1. **Repository:** Push this repository to GitHub or GitLab.
2. **Create New Web Service:** On the [Render Dashboard](https://dashboard.render.com), select **New > Web Service**.
3. **Configuration:**
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `gunicorn app:app`
4. **Environment Variables:**
   Add these in the **Environment** tab on Render:
   | Variable | Value / Description |
   | :--- | :--- |
   | `NEWSDATA_API_KEY` | Your NewsData.io API key |
   | `EVENTREGISTRY_API_KEY` | Your Event Registry API key |
   | `GEMINI_API_KEY` | Your Google Gemini API key |
   | `CACHE_TTL_SECONDS` | `3600` |
   | `SECRET_KEY` | Strong random secret string |
   | `PORT` | `10000` (set automatically by Render) |

---

## 🛠️ Local Development Setup

### 1. Clone & Install Dependencies
```bash
git clone <your-repo-url>
cd "IMP News App"
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy the template and fill in your API credentials:
```bash
cp .env.example .env
```

Your `.env` file should include:
```env
NEWSDATA_API_KEY=your_newsdata_key_here
EVENTREGISTRY_API_KEY=your_eventregistry_key_here
GEMINI_API_KEY=your_gemini_key_here
CACHE_TTL_SECONDS=3600
PORT=5000
FLASK_DEBUG=1
```

> **Get a free Google Gemini API key:** [Google AI Studio](https://aistudio.google.com/app/apikey)

### 3. Run Locally
```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## 🧪 Testing

Run the automated test suite covering all routes, pagination, SQLite bookmarking, Gemini router, and health diagnostics:

```bash
python test_app.py
```

Expected output:
```text
=== STARTING IMP NEWS APP TESTS ===
[1/7] Testing Home Route '/' ... -> PASSED
[2/7] Testing Core Category Routes ... -> PASSED
[3/7] Testing Category Pagination ... -> PASSED
[4/7] Testing SQL Database: Save Post feature ... -> PASSED
[5/7] Testing Saved Posts Route '/saved' ... -> PASSED
[6/7] Testing Ask Gemini AI Endpoint '/api/gemini/action' ... -> PASSED
[7/7] Testing /api/health ... -> PASSED
=== ALL 7 TESTS PASSED SUCCESSFULLY! ===
```

---

## 📄 License
Open-source under the MIT License. Built for the community.
