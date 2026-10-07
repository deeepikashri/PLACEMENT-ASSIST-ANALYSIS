"""
Live job postings integration (optional).

Fetches real, currently-open remote job postings from the free,
keyless Remotive public API (https://remotive.com/api/remote-jobs) so
the placement organization can import a real posting as a starting
point instead of typing every field by hand. No API key or account is
required for this one.

Entirely optional: on any failure (no network, API down, etc.) callers
get an empty list back and the rest of the app -- manually-entered jobs
-- is unaffected.
"""

import re
from typing import Any, Dict, List

import requests

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
_REQUEST_TIMEOUT_SECONDS = 8
_DESCRIPTION_CHAR_LIMIT = 2000


def _strip_html(raw_html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw_html or "")
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def search_live_jobs(query: str = "", limit: int = 15) -> List[Dict[str, Any]]:
    """
    Search live remote job postings. Returns a list of dicts shaped for
    direct use with database.add_job()'s company_name/job_title/description
    fields, plus a "url" and "category" for display purposes only.
    Returns [] on any error so this integration can never break job
    management -- it's an optional convenience, not a dependency.
    """
    try:
        params = {"search": query} if query.strip() else {}
        response = requests.get(REMOTIVE_API_URL, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    results = []
    for job in jobs[:limit]:
        results.append({
            "company_name": (job.get("company_name") or "").strip()[:255],
            "job_title": (job.get("title") or "").strip()[:255],
            "description": _strip_html(job.get("description", ""))[:_DESCRIPTION_CHAR_LIMIT],
            "minimum_experience": 0,
            "url": job.get("url", ""),
            "category": job.get("category", ""),
        })
    return results
