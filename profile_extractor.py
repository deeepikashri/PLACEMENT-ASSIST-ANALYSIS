"""
Candidate profile extraction (spec section 8).

Best-effort, regex/heuristic based extraction of:
    - Name
    - Email
    - Phone
    - Education
    - Experience (years)
    - Projects
    - Certifications

None of this uses ML/LLMs — this is intentionally simple heuristic
parsing. Because resumes vary wildly in layout, the calling UI must
always let the user review and edit these fields (spec requirement).
"""

import re
from typing import Dict, List, Optional

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3}[-.\s]?\d{3,4}[-.\s]?\d{0,4}")
EXPERIENCE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|year|yrs|yr)s?\s*(?:of)?\s*(?:experience|exp)?",
    re.IGNORECASE,
)

EDUCATION_KEYWORDS = [
    "bachelor", "b.tech", "btech", "b.e", "bsc", "b.sc", "master", "m.tech",
    "mtech", "msc", "m.sc", "mba", "phd", "ph.d", "diploma", "university",
    "college", "institute of technology",
]

SECTION_HEADERS = {
    "education": ["education", "academic background", "qualifications"],
    "projects": ["projects", "academic projects", "personal projects"],
    "certifications": ["certifications", "certificates", "licenses & certifications"],
    "experience": ["experience", "work experience", "professional experience", "employment history"],
    "skills": ["skills", "technical skills", "core competencies"],
    # Not individually parsed for content, but recognized so sections above
    # (education, certifications, etc.) know where to stop instead of
    # swallowing everything after them to the end of the document.
    "other": [
        "leadership", "soft skills", "extracurricular", "achievements",
        "awards", "activities", "summary", "professional summary",
        "objective", "career objective", "hobbies", "interests",
        "languages", "references", "publications", "volunteer",
        "volunteering", "training",
    ],
}


# A header line is short by nature ("PROJECTS", "CERTIFICATIONS & TRAINING").
# This length guard stops a body/bullet line that merely happens to START
# with a keyword (e.g. "Projects I'm most proud of include...") from being
# mistaken for a section header.
_MAX_HEADER_LINE_LEN = 40


def _is_header_line(cleaned: str, keywords: List[str]) -> bool:
    """
    True if `cleaned` (a lowercased, stripped line) IS a section header for
    one of `keywords` — either an exact match, or the keyword plus a short
    trailing qualifier like " & training" / " (2024)" / ":". Real resumes
    routinely combine two related headers ("CERTIFICATIONS & TRAINING",
    "LICENSES & CERTIFICATIONS", "PROJECTS (2023-2024)"), so a strict
    equality check silently fails to recognize the section at all.
    """
    if len(cleaned) > _MAX_HEADER_LINE_LEN:
        return False
    return any(cleaned == kw or cleaned.startswith(kw + " ") for kw in keywords)


def _find_section(text: str, header_keywords: List[str]) -> str:
    """
    Return the text block that follows any of the given section header
    keywords, up until the next likely section header. Best-effort only.
    """
    lines = text.split("\n")
    lower_lines = [ln.strip().lower() for ln in lines]

    start_idx = None
    for i, line in enumerate(lower_lines):
        cleaned = line.strip(":- ").strip()
        if _is_header_line(cleaned, header_keywords):
            start_idx = i + 1
            break

    if start_idx is None:
        return ""

    all_headers = [kw for kws in SECTION_HEADERS.values() for kw in kws]
    end_idx = len(lines)
    for j in range(start_idx, len(lines)):
        candidate = lower_lines[j].strip(":- ").strip()
        if _is_header_line(candidate, all_headers):
            end_idx = j
            break

    return "\n".join(lines[start_idx:end_idx]).strip()


def extract_name(text: str) -> str:
    """
    Heuristic: the first non-empty line that looks like a plain human
    name (no digits, no @, short length) is likely the candidate's name,
    since most resumes lead with the name.
    """
    for line in text.split("\n")[:8]:
        candidate = line.strip()
        if not candidate:
            continue
        if EMAIL_RE.search(candidate) or PHONE_RE.search(candidate):
            continue
        if any(ch.isdigit() for ch in candidate):
            continue
        words = candidate.split()
        if 1 <= len(words) <= 4 and all(w.replace(".", "").isalpha() for w in words):
            return candidate.title()
    return ""


def extract_email(text: str) -> str:
    match = EMAIL_RE.search(text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    match = PHONE_RE.search(text)
    return match.group(0).strip() if match else ""


def extract_experience_years(text: str) -> float:
    """
    Find the largest "X years of experience" style mention. If nothing
    is found, default to 0 (fresher / not stated).
    """
    matches = EXPERIENCE_RE.findall(text)
    years = [float(m) for m in matches if m]
    return max(years) if years else 0.0


def extract_education(text: str) -> str:
    section = _find_section(text, SECTION_HEADERS["education"])
    if section:
        return section[:500]

    # Fallback: scan for education keywords anywhere in the document
    lines = text.split("\n")
    matched_lines = [
        ln.strip() for ln in lines
        if any(kw in ln.lower() for kw in EDUCATION_KEYWORDS)
    ]
    return "\n".join(matched_lines[:5])


_BULLET_RE = re.compile(r"^[-•*]\s*")

# Matches a "Tech Stack: X, Y, Z" / "Technologies Used: ..." / "Tools: ..."
# style line so it can be routed into its own `technologies` field instead
# of getting dumped into the description text.
_TECH_LINE_RE = re.compile(
    r"^(?:tech(?:nical)?\s*stack|technolog(?:y|ies)(?:\s*used)?|tools(?:\s*used)?|stack)\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)

# A line ending in . ! or ? is treated as a *complete* sentence/title. This
# is the key signal used to tell a genuine new project title apart from a
# PDF text-wrap continuation of the previous bullet (see below).
_SENTENCE_END_RE = re.compile(r"[.!?]$")


def _truncate_at_word(text: str, limit: int) -> str:
    """Cut text to at most `limit` chars without slicing a word in half."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rsplit("\n", 1)[0]
    return cut.rstrip(",.;: ") + "…"


def extract_projects(text: str) -> List[Dict[str, str]]:
    """
    Group each project title with the bullet/description lines (and any
    "Tech Stack:" line) that follow it into ONE project entry.

    The tricky part: when PyMuPDF extracts text from a PDF, a long bullet
    point often wraps onto a second physical line with NO bullet marker
    on the continuation (e.g. "...work-from-home policies" / "using
    company HR documents."). Naively treating every plain line after a
    bullet as a new project title turns each wrapped continuation into
    its own fake, title-less "project".

    Fix: a plain (non-bullet) line only starts a NEW project if the
    previous content line ended with sentence-terminal punctuation
    (. ! ?) — i.e. the previous bullet/title was actually finished — or
    if it follows a blank line / the start of the section. Otherwise
    it's a wrapped continuation and gets merged back onto the previous
    line instead of becoming its own entry.

    A "Tech Stack:" / "Technologies:" / "Tools:" line is detected
    separately and stored in `technologies`, not mixed into the
    description.
    """
    section = _find_section(text, SECTION_HEADERS["projects"])
    if not section:
        return []

    projects: List[Dict[str, str]] = []
    current_title: Optional[str] = None
    current_tech: str = ""
    current_desc_lines: List[str] = []
    prev_ends_sentence = True  # so the very first content line always starts a project
    prev_was_blank = True

    def flush():
        if current_title:
            projects.append({
                "name": current_title.strip()[:100],
                "description": _truncate_at_word(
                    "\n".join(current_desc_lines).strip(), 800
                ),
                "technologies": current_tech.strip(", ").strip()[:200],
            })

    for raw_line in section.split("\n"):
        stripped = raw_line.strip()

        if not stripped:
            prev_was_blank = True
            continue

        is_bullet = bool(_BULLET_RE.match(stripped))

        if is_bullet:
            content = _BULLET_RE.sub("", stripped).strip()
            if current_title is None:
                # A bullet before any title was seen — treat it as its own project.
                current_title = content
            else:
                current_desc_lines.append(content)
            prev_ends_sentence = bool(_SENTENCE_END_RE.search(content))
            prev_was_blank = False
            continue

        tech_match = _TECH_LINE_RE.match(stripped)
        if tech_match and current_title is not None:
            addition = tech_match.group(1).strip()
            current_tech = f"{current_tech}, {addition}" if current_tech else addition
            prev_ends_sentence = bool(_SENTENCE_END_RE.search(stripped))
            prev_was_blank = False
            continue

        if current_title is None or prev_was_blank or prev_ends_sentence:
            # The previous content line was genuinely finished (or this is
            # the very first line / follows a blank line) -> new project.
            flush()
            current_title = stripped
            current_tech = ""
            current_desc_lines = []
        else:
            # Previous content line ended mid-sentence -> this is a
            # wrapped continuation, not a new project.
            if current_desc_lines:
                # Merge back onto the bullet/paragraph line it wrapped from.
                current_desc_lines[-1] = f"{current_desc_lines[-1]} {stripped}".strip()
            else:
                # No description started yet (title has no trailing bullet
                # or Tech Stack line before the wrap) -> this is the start
                # of a non-bulleted, paragraph-style description, NOT the
                # title wrapping onto a second line. Titles essentially
                # never wrap across lines in practice, so treat this as
                # the first description line.
                current_desc_lines.append(stripped)

        prev_ends_sentence = bool(_SENTENCE_END_RE.search(stripped))
        prev_was_blank = False

    flush()
    return projects[:10]


def extract_certifications(text: str) -> List[Dict[str, str]]:
    section = _find_section(text, SECTION_HEADERS["certifications"])
    if not section:
        return []

    certs = []
    lines = [ln.strip(" -•*") for ln in section.split("\n") if ln.strip()]
    for line in lines[:10]:
        certs.append({"name": line[:150], "issuer": ""})
    return certs


def extract_candidate_profile(cleaned_text: str) -> Dict:
    """
    Run all heuristic extractors and return a single profile dict.
    The caller (Streamlit UI) MUST allow the user to review/edit this,
    since heuristic parsing of arbitrary resume layouts is inherently
    imperfect.
    """
    return {
        "name": extract_name(cleaned_text),
        "email": extract_email(cleaned_text),
        "phone": extract_phone(cleaned_text),
        "education": extract_education(cleaned_text),
        "experience_years": extract_experience_years(cleaned_text),
        "projects": extract_projects(cleaned_text),
        "certifications": extract_certifications(cleaned_text),
    }
