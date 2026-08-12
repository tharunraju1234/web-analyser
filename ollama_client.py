"""
Wrapper around a local Ollama instance. Handles all "understand this like a
human would" tasks: grammar quality, landing page first-impression rating,
plain-language summaries, and pricing justification.
Requires Ollama running locally with a model pulled, e.g. `ollama pull llama3.1:8b`.
"""
import json
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"  # change to whatever model you've pulled: `ollama list`


def _call_ollama(prompt: str, timeout: int = 60) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.3}},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def _parse_json_response(raw: str, fallback: dict) -> dict:
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return fallback


def analyze_grammar(text: str) -> dict:
    if not text or len(text.strip()) < 20:
        return {"score": None, "issue_count": 0, "examples": [], "summary": "Not enough text on the page to assess."}

    prompt = f"""You are a proofreader assessing the writing quality of website text.

TEXT:
\"\"\"{text[:3000]}\"\"\"

Assess grammar, spelling, and clarity. Respond with ONLY valid JSON, no other text:
{{"score": <int 0-100, 100=flawless>, "issue_count": <int>, "examples": [<up to 3 short strings, one issue each>], "summary": "<one sentence overall assessment>"}}"""

    raw = _call_ollama(prompt)
    return _parse_json_response(raw, {"score": None, "issue_count": 0, "examples": [], "summary": "Could not parse assessment."})


def rate_landing_page(text: str) -> dict:
    if not text or len(text.strip()) < 20:
        return {"rating": None, "strengths": [], "weaknesses": [], "summary": "Not enough text to evaluate."}

    prompt = f"""You are a UX and marketing expert evaluating a website's landing page, based only on its text content (you cannot see the visual design).

TEXT:
\"\"\"{text[:3000]}\"\"\"

From a first-time visitor's perspective: how clear is the value proposition, how trustworthy does it feel, how quickly could someone understand what this business offers and what to do next.

Respond with ONLY valid JSON:
{{"rating": <int 1-10>, "strengths": [<up to 3 short strings>], "weaknesses": [<up to 3 short strings>], "summary": "<2-3 sentence overall impression>"}}"""

    raw = _call_ollama(prompt)
    return _parse_json_response(raw, {"rating": None, "strengths": [], "weaknesses": [], "summary": "Could not parse rating."})


def summarize_in_own_words(text: str, context: str = "this page") -> str:
    if not text or len(text.strip()) < 20:
        return "Not enough text found on this page to summarize."

    prompt = f"""Read the following text from {context} and explain, in your own words (2-4 sentences, do not quote directly), what it communicates about the company.

TEXT:
\"\"\"{text[:3000]}\"\"\"

Respond with ONLY the summary, no preamble, no quotation marks."""

    return _call_ollama(prompt).strip()


def analyze_pricing(text: str) -> dict:
    if not text or len(text.strip()) < 20:
        return {"plans_detected": [], "assessment": "No pricing information found on this page."}

    prompt = f"""You are a pricing strategy analyst. Read this pricing page content and assess whether the pricing seems reasonably justified given what's offered.

TEXT:
\"\"\"{text[:3000]}\"\"\"

Respond with ONLY valid JSON:
{{"plans_detected": [<short strings naming plans/tiers found, if any>], "assessment": "<3-4 sentence assessment of whether the pricing seems justified by the value offered, and why>"}}"""

    raw = _call_ollama(prompt)
    return _parse_json_response(raw, {"plans_detected": [], "assessment": "Could not parse pricing analysis."})