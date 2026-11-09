import sys
from unittest.mock import patch
from app import app, CATEGORIES
import database

def run_tests():
    print("=== STARTING IMP NEWS APP TESTS ===")
    client = app.test_client()
    
    sample_articles = [
        {
            "id": f"art-{i}",
            "title": f"Story {i}: Breakthrough in Quantum Tech and Global Developments",
            "description": "Comprehensive details explaining the event, its impacts, and what happens next.",
            "content": "Full article context for analysis and reader comprehension.",
            "url": f"https://example.com/story-{i}",
            "image": "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?auto=format&fit=crop&w=800&q=80",
            "source_name": "Verified Source",
            "published_at": "10m ago",
            "category_name": "Tech News",
            "category_slug": "tech",
            "is_breaking": (i == 0)
        }
        for i in range(5)
    ]

    # 1. Test Home Route with articles
    print("[1/7] Testing Home Route '/' ...")
    with patch('app.get_articles_for_category', return_value=sample_articles):
        resp = client.get('/')
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        html = resp.get_data(as_text=True)
        assert "Imp News" in html, "Brand title missing in home page"
        assert "Tamil News" in html, "Tamil category missing in home page"
        assert "English News" in html, "English category missing in home page"
        assert "Tech News" in html, "Tech category missing in home page"
        assert "Mysterious Tech News" in html, "Mysterious Tech category missing in home page"
        assert "Ask Gemini" in html, "Ask Gemini feature button missing in home page"
        assert "Save" in html, "Save post button missing in home page"
    print("  -> PASSED: Home route rendered correctly with all category previews & feature buttons.")

    # 2. Test All 5 Category Routes
    print("[2/7] Testing Core Category Routes ...")
    with patch('app.get_articles_for_category', return_value=sample_articles):
        for slug, meta in CATEGORIES.items():
            resp = client.get(f'/category/{slug}')
            assert resp.status_code == 200, f"Expected 200 for /category/{slug}, got {resp.status_code}"
            cat_html = resp.get_data(as_text=True)
            expected_name = meta['name'].replace('&', '&amp;')
            assert expected_name in cat_html or meta['name'] in cat_html, f"Category name '{meta['name']}' not in response"
            assert "Ask Gemini" in cat_html, f"Ask Gemini button missing in /category/{slug}"
            assert "Save" in cat_html, f"Save button missing in /category/{slug}"
            print(f"  -> PASSED: /category/{slug} loaded successfully.")

    # 3. Test Pagination
    print("[3/7] Testing Category Pagination ...")
    dummy_pagination = [
        {"id": f"art-{i}", "title": f"Story {i}", "description": "Desc", "url": f"https://example.com/{i}", "image": "", "source_name": "Test", "published_at": "Recent", "is_breaking": False}
        for i in range(25)
    ]
    with patch('app.get_articles_for_category', return_value=dummy_pagination):
        resp_p2 = client.get('/category/tamil?page=2')
        assert resp_p2.status_code == 200, f"Expected 200 for page 2, got {resp_p2.status_code}"
        p2_html = resp_p2.get_data(as_text=True)
        assert "Previous" in p2_html, "Pagination controls missing on page 2"
    print("  -> PASSED: Pagination works on category feeds.")

    # 4. Test SQL Database: Save Post & Unsave Post APIs
    print("[4/7] Testing SQL Database: Save Post feature ...")
    test_article = {
        "id": "sql-test-123",
        "title": "Quantum Leap in AI News Analysis",
        "description": "Scientists announce a major breakthrough in natural language news comprehension.",
        "url": "https://example.com/quantum-leap-ai",
        "image": "https://example.com/img.jpg",
        "source_name": "Science Journal",
        "published_at": "Just now",
        "category_name": "Tech News",
        "category_slug": "tech"
    }
    
    # Save the post
    resp_save = client.post('/api/save-post', json=test_article)
    assert resp_save.status_code == 200
    save_data = resp_save.get_json()
    assert save_data['success'] is True
    assert save_data['saved'] is True
    assert save_data['saved_count'] >= 1
    assert database.is_article_saved(article_id="sql-test-123") is True
    print("  -> PASSED: Article successfully saved to SQLite database.")

    # 5. Test Saved Posts Route '/saved'
    print("[5/7] Testing Saved Posts Route '/saved' ...")
    resp_saved_page = client.get('/saved')
    assert resp_saved_page.status_code == 200
    saved_html = resp_saved_page.get_data(as_text=True)
    assert "Quantum Leap in AI News Analysis" in saved_html
    assert "Saved Posts" in saved_html
    assert "Ask Gemini" in saved_html
    print("  -> PASSED: /saved rendered bookmarked articles from SQL database.")

    # Toggle save (should un-save)
    resp_toggle = client.post('/api/save-post', json={"id": "sql-test-123", "url": "https://example.com/quantum-leap-ai"})
    assert resp_toggle.status_code == 200
    toggle_data = resp_toggle.get_json()
    assert toggle_data['saved'] is False
    assert database.is_article_saved(article_id="sql-test-123") is False
    print("  -> PASSED: Toggle un-save successfully removed post from SQL database.")

    # 6. Test Ask Gemini AI API Router
    print("[6/7] Testing Ask Gemini AI Endpoint '/api/gemini/action' ...")
    resp_gemini = client.post('/api/gemini/action', json={
        "action": "summary",
        "title": "Global Tech Summit 2026",
        "description": "Leaders gather to discuss artificial intelligence ethics and safety regulations."
    })
    assert resp_gemini.status_code == 200
    gemini_data = resp_gemini.get_json()
    assert 'success' in gemini_data
    print("  -> PASSED: /api/gemini/action router correctly structured and resilient.")

    # 7. Test Diagnostic Health Route
    print("[7/7] Testing /api/health ...")
    resp_health = client.get('/api/health')
    assert resp_health.status_code == 200
    data = resp_health.get_json()
    assert data['app_name'] == 'Imp News App'
    assert 'sql_database' in data
    assert 'saved_posts_count' in data
    assert 'tamil' in data['categories']
    assert 'english' in data['categories']
    assert 'tech' in data['categories']
    print("  -> PASSED: /api/health returned complete diagnostic payload.")

    print("\n=== ALL 7 TESTS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    run_tests()
