"""
Optional LLM-based candidate profile extraction.

This is an OPTIONAL enhancement layer on top of the deterministic,
regex-based extractor in `profile_extractor.py`. It uses Google's
Gemini API (free tier via Google AI Studio -- https://aistudio.google.com/apikey,
no credit card required) and is only used when GEMINI_API_KEY is set;
otherwise, and on any failure, it returns None and the caller falls
back to the heuristic extractor. The Streamlit UI always lets the
candidate review/edit the final fields either way.

Design note: this module only touches profile *fields* (name, email,
phone, education, experience, projects, certifications). Skill
extraction/matching used for scoring stays 100% deterministic per the
project's core design principle (see README) -- the LLM is never the
source of truth for skill-gap scoring.
"""

import json
import os
import re
from typing import Dict, List, Optional

# gemini-2.0-flash is on Google AI Studio's free tier (no billing account
# required) as of this writing. Override with GEMINI_MODEL if desired.
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Cap how much resume text we send, both to stay within free-tier limits
# and because candidate profiles don't need more than this to extract reliably.
_MAX_INPUT_CHARS = 12000

_SYSTEM_PROMPT = (
    "You extract structured candidate profile data from resume text. "
    "Respond with ONLY a single valid JSON object, no markdown code fences, "
    "no commentary before or after it."
)

_USER_PROMPT_TEMPLATE = """Extract the following fields from this resume text and return them as a
JSON object with EXACTLY these keys:

- "name": string, the candidate's full name (or "" if not found)
- "email": string, the candidate's email address (or "" if not found)
- "phone": string, the candidate's phone number (or "" if not found)
- "education": string, a short summary of the candidate's education (or "")
- "experience_years": number, total years of professional experience (0 if fresher/not stated)
- "projects": array of objects, each with "name", "description", "technologies"
  (max 10 projects, description max ~500 characters)
- "certifications": array of objects, each with "name", "issuer" (max 10)

Resume text:
---
{resume_text}
---

Return ONLY the JSON object described above.
"""


def is_llm_configured() -> bool:
    """True if a Gemini API key is available in the environment."""
    return bool(os.getenv("GEMINI_API_KEY"))


def _strip_code_fences(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _coerce_profile(data: Dict) -> Dict:
    """Clamp/validate the LLM's JSON into the same shape profile_extractor.py produces."""

    def _str(key: str, limit: int = 500) -> str:
        val = data.get(key, "")
        return str(val).strip()[:limit] if val else ""

    try:
        experience_years = float(data.get("experience_years") or 0)
    except (TypeError, ValueError):
        experience_years = 0.0
    experience_years = max(0.0, min(experience_years, 50.0))

    def _list_of_dicts(key: str, field_map: List[str], limit: int) -> List[Dict[str, str]]:
        raw_list = data.get(key) or []
        if not isinstance(raw_list, list):
            return []
        cleaned = []
        for item in raw_list[:limit]:
            if not isinstance(item, dict):
                continue
            cleaned.append({field: str(item.get(field, "")).strip()[:800] for field in field_map})
        return cleaned

    return {
        "name": _str("name", 150),
        "email": _str("email", 150),
        "phone": _str("phone", 50),
        "education": _str("education", 500),
        "experience_years": experience_years,
        "projects": _list_of_dicts("projects", ["name", "description", "technologies"], 10),
        "certifications": _list_of_dicts("certifications", ["name", "issuer"], 10),
    }


def extract_profile_with_llm(resume_text: str) -> Optional[Dict]:
    """
    Attempt LLM-based extraction via Google's Gemini API (free tier).
    Returns a profile dict shaped exactly like
    `profile_extractor.extract_candidate_profile()`'s output, or None if
    the LLM is not configured, the call fails, or the response can't be
    parsed -- in every "None" case the caller should silently fall back
    to the deterministic heuristic extractor.
    """
    if not resume_text or not resume_text.strip():
        return None
    if not is_llm_configured():
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        return None

    try:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(LLM_MODEL, system_instruction=_SYSTEM_PROMPT)
        response = model.generate_content(
            _USER_PROMPT_TEMPLATE.format(resume_text=resume_text[:_MAX_INPUT_CHARS]),
            generation_config={
                "response_mime_type": "application/json",
                "max_output_tokens": 2000,
            },
        )
        raw_text = (response.text or "").strip()
        if not raw_text:
            return None

        parsed = json.loads(_strip_code_fences(raw_text))
        if not isinstance(parsed, dict):
            return None
        return _coerce_profile(parsed)
    except Exception:
        # Any failure (network, auth, quota, malformed JSON, etc.) -> caller falls back.
        return None
