"""
Groq AI integration.

Used at post-submission time (and, for a live pre-submit check, via
/posts/api/analyze) to:
  - suggest a category for the report
  - flag content that looks like spam/hate-speech/abuse for admin review
  - warn the submitter if their own text contains information that could
    identify them or a third party (phone numbers, emails, full names
    volunteered alongside "my name is...", home addresses, etc.)

This is entirely best-effort and NEVER a hard dependency: if
GROQ_API_KEY is unset, the request times out, or the response can't be
parsed, callers get a safe default (category "Other", not flagged, no
PII warning) and the post still goes through unaffected. AI assistance
augments moderation and UX -- it must never block or gate core
functionality of an anonymous submission platform.
"""
import json
import logging

import requests

from constants import POST_CATEGORIES

logger = logging.getLogger("whistlevault.ai")

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 10

_SYSTEM_PROMPT = (
    "You are a careful content triage assistant for an anonymous whistleblower "
    "submission platform. Analyze the report without rewriting or inventing facts. "
    "A person's name, an organization name, or a named person involved in an allegation "
    "is not by itself sensitive personal information and should not trigger a PII flag. "
    "Do flag phone numbers, email addresses, home addresses, government IDs, bank or "
    "account numbers, license plates, passwords, access tokens, or other identifying numbers. "
    "Given a post title and body, respond with ONLY "
    "a JSON object (no markdown fences, no commentary) with these exact "
    "keys:\n"
    f'- "category": one of {json.dumps(POST_CATEGORIES)}\n'
    '- "flagged": true if the content is spam, hate speech, harassment, '
    "or clearly not a genuine report, else false\n"
    '- "flag_reason": short reason if flagged, else an empty string\n'
    '- "pii_detected": true if the text contains information that could '
    "identify the submitter or another private person, including phone numbers, email addresses, "
    "home addresses, national ID / SSN-style numbers, bank or account numbers, license plates, "
    "passwords, or access tokens, else false\n"
    '- "pii_warning": if pii_detected, one short sentence to show the '
    "submitter explaining what to consider redacting, else an empty "
    "string\n"
    "Respond with raw JSON only, nothing else."
)


class AIAnalysisResult:
    def __init__(
        self,
        category="Other",
        flagged=False,
        flag_reason="",
        pii_detected=False,
        pii_warning="",
        available=True,
    ):
        self.category = category
        self.flagged = flagged
        self.flag_reason = flag_reason
        self.pii_detected = pii_detected
        self.pii_warning = pii_warning
        self.available = available  # False if AI could not be reached/parsed

    def to_dict(self):
        return {
            "category": self.category,
            "flagged": self.flagged,
            "flag_reason": self.flag_reason,
            "pii_detected": self.pii_detected,
            "pii_warning": self.pii_warning,
            "available": self.available,
        }


def _extract_json(raw: str) -> dict:
    """Parses the model's JSON reply, tolerating stray text around it."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def analyze_post(app, title: str, content: str) -> AIAnalysisResult:
    """
    Calls Groq's OpenAI-compatible chat completions endpoint.

    `app` is the Flask app (or current_app) so config (API key, model
    name) is read consistently with the rest of the codebase rather than
    from module-level globals.
    """
    api_key = app.config.get("GROQ_API_KEY")
    if not api_key:
        return AIAnalysisResult(available=False)

    model = app.config.get("GROQ_MODEL", "openai/gpt-oss-20b")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Title: {title}\n\nBody: {content[:4000]}"},
        ],
        "temperature": 0.1,
        "max_tokens": 300,
    }

    try:
        resp = requests.post(
            GROQ_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        raw_content = resp.json()["choices"][0]["message"]["content"]
        parsed = _extract_json(raw_content)
    except Exception:
        logger.warning("Groq AI analysis unavailable; using safe defaults", exc_info=True)
        return AIAnalysisResult(available=False)

    category = parsed.get("category")
    if category not in POST_CATEGORIES:
        category = "Other"

    return AIAnalysisResult(
        category=category,
        flagged=bool(parsed.get("flagged", False)),
        flag_reason=str(parsed.get("flag_reason") or "")[:500],
        pii_detected=bool(parsed.get("pii_detected", False)),
        pii_warning=str(parsed.get("pii_warning") or "")[:500],
        available=True,
    )
