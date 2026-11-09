"""
gemini_service.py - Google Gemini AI Service for Imp News App
Handles:
1. News Summarization (3 concise bullet points)
2. Simple English Translation/Simplification (Plain, beginner-friendly explanations)
3. News Doubts Q&A (Interactive answering of reader questions about stories)
"""

import os
import logging
from typing import Dict, Any, Optional
import requests
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Gemini API Endpoint configuration
GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.8-flash"]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def get_gemini_api_key() -> str:
    """Retrieve active Gemini API Key from environment dynamically, reloading .env if modified."""
    load_dotenv(override=True)
    return os.getenv("GEMINI_API_KEY", "").strip()


def call_gemini_api(prompt: str) -> Dict[str, Any]:
    """
    Direct HTTP REST call to Google Gemini API using requests.
    Tries current fast model with graceful fallback.
    """
    api_key = get_gemini_api_key()
    if not api_key or api_key == "your_gemini_api_key_here":
        return {
            "success": False,
            "error": "Gemini API key is not configured. Please add GEMINI_API_KEY to your .env file."
        }

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "topP": 0.95,
            "maxOutputTokens": 1000
        }
    }

    last_error = ""
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            logger.info(f"[GEMINI REQUEST] Calling model '{model}'...")
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "").strip()
                        return {"success": True, "text": text, "model": model}
                return {"success": False, "error": "Gemini returned an empty response."}
            
            elif response.status_code == 400:
                err_json = response.json().get("error", {})
                last_error = err_json.get("message", response.text)
                logger.warning(f"Gemini API {model} HTTP 400: {last_error}")
                continue  # Try next model if model name or parameter wasn't recognized

            elif response.status_code == 403 or response.status_code == 401:
                return {
                    "success": False,
                    "error": "Gemini API key is invalid or unauthorized. Please verify your GEMINI_API_KEY in .env."
                }
            
            elif response.status_code == 429:
                return {
                    "success": False,
                    "error": "Gemini rate limit reached. Please wait a moment before trying again."
                }
            else:
                last_error = f"HTTP {response.status_code}: {response.text}"
                logger.warning(f"Gemini {model} returned {last_error}")

        except requests.exceptions.Timeout:
            last_error = "Gemini request timed out. Please retry."
        except requests.exceptions.RequestException as exc:
            last_error = f"Network connection error: {exc}"
        except Exception as exc:
            last_error = f"Unexpected error: {exc}"

    return {"success": False, "error": last_error or "Unable to reach Gemini AI service."}


def summarize_article(title: str, description: str, content: str = "") -> Dict[str, Any]:
    """Generate a clean 3-bullet point executive summary of the news story."""
    prompt = f"""You are an expert news editor for Imp News App.
Provide a clear, engaging, and accurate 3-bullet summary of the following news story.
Focus on:
1. What happened (The core event)
2. Why it matters / The background context
3. Key impact or what happens next

Format your response as 3 bullet points starting with a relevant emoji.

Article Title: {title}
Article Summary/Snippet: {description}
Full Content (if available): {content or 'N/A'}

Provide ONLY the 3 bullet points, nothing else."""

    result = call_gemini_api(prompt)
    if result.get("success"):
        return {"success": True, "result": result["text"], "action": "summary", "model": result.get("model")}
    return {"success": False, "error": result.get("error")}


def simplify_article(title: str, description: str, content: str = "") -> Dict[str, Any]:
    """
    Explain the news in simple, friendly, 5th-grade English.
    Breaks down jargon, difficult acronyms, and complex geopolitical or technical topics.
    """
    prompt = f"""You are an encouraging teacher and explainer for Imp News App.
Many readers find news filled with difficult jargon, complex political terms, or technical buzzwords hard to understand.
Explain this news in very Simple English (plain words, 5th-grade level) that anyone can easily follow.

Structure your answer:
1. 💡 **What is this story about?** (Explain in 2 simple sentences)
2. 🔍 **Difficult terms explained simply** (If any difficult concepts or acronyms appear, explain them in plain English)
3. 🌍 **Why should you care?** (How this impacts everyday people)

Article Title: {title}
Article Summary/Snippet: {description}
Full Content (if available): {content or 'N/A'}

Keep sentences short, clear, and friendly."""

    result = call_gemini_api(prompt)
    if result.get("success"):
        return {"success": True, "result": result["text"], "action": "simple_english", "model": result.get("model")}
    return {"success": False, "error": result.get("error")}


def ask_doubt_about_article(title: str, description: str, question: str, content: str = "") -> Dict[str, Any]:
    """Answer a user's specific question or doubt about the news story."""
    if not question or not question.strip():
        return {"success": False, "error": "Please provide a question or doubt about the article."}

    prompt = f"""You are a helpful and knowledgeable news assistant for Imp News App.
A reader has a specific question or doubt about the following news story.
Answer their question directly, accurately, and objectively based on the article facts and context.
If the article does not contain enough info, give the best factual context available and clarify what is known.

Article Title: {title}
Article Summary/Snippet: {description}
Full Content (if available): {content or 'N/A'}

Reader's Question:
"{question.strip()}"

Give a direct, concise, and helpful answer (1-2 short paragraphs or clean bullet points)."""

    result = call_gemini_api(prompt)
    if result.get("success"):
        return {"success": True, "result": result["text"], "action": "ask_doubt", "model": result.get("model")}
    return {"success": False, "error": result.get("error")}


def process_gemini_request(action: str, title: str, description: str, content: str = "", question: str = "") -> Dict[str, Any]:
    """Unified router for all Gemini news actions."""
    if action == "summary":
        return summarize_article(title, description, content)
    elif action == "simple_english":
        return simplify_article(title, description, content)
    elif action == "ask_doubt":
        return ask_doubt_about_article(title, description, question, content)
    else:
        return {"success": False, "error": f"Unknown action: {action}"}

