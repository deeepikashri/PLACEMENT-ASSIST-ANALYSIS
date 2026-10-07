"""
Dictionary-based skill extraction and normalization.

Design goal (per spec section 7):
The BASIC dictionary-based extraction must work without any external
LLM API. It matches a controlled vocabulary of skills (and their
common aliases/variations) against cleaned resume text using
word-boundary-safe regex matching, so it does not blindly treat every
word as a skill.

An OPTIONAL semantic layer (Sentence Transformers) can later be added
for fuzzy/semantic matching, but it is not required for the extractor
to function (see section 33 - future extensibility).
"""

import json
import re
from typing import Dict, List, Set

from utils.paths import SKILL_DICTIONARY_PATH


def load_skill_dictionary() -> Dict[str, Dict]:
    """Load the editable, controlled skill dictionary from disk."""
    with open(SKILL_DICTIONARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_alias_lookup(skill_dict: Dict[str, Dict]) -> Dict[str, List[str]]:
    """
    Build a mapping of canonical_skill -> [alias_pattern, ...]
    Longer aliases are matched first to avoid partial overlaps
    (e.g. "tensorflow/keras" should yield both TensorFlow and Keras).
    """
    lookup = {}
    for canonical, meta in skill_dict.items():
        aliases = set(a.lower().strip() for a in meta.get("aliases", []))
        aliases.add(canonical.lower())
        lookup[canonical] = sorted(aliases, key=len, reverse=True)
    return lookup


def _alias_to_regex(alias: str) -> re.Pattern:
    """
    Convert an alias into a safe regex with word boundaries.
    Handles aliases containing special characters like '++', '.', '/'.
    """
    escaped = re.escape(alias)
    # Allow flexible whitespace where the alias has a literal space
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9])", re.IGNORECASE)


def extract_skills(resume_text: str) -> List[str]:
    """
    Extract canonical skill names present in the resume text.

    Returns a sorted, de-duplicated list of canonical skill names, e.g.
    ["Machine Learning", "NumPy", "Pandas", "Python", "Scikit-learn", "TensorFlow"]
    """
    if not resume_text:
        return []

    skill_dict = load_skill_dictionary()
    alias_lookup = _build_alias_lookup(skill_dict)
    text = resume_text.lower()

    found: Set[str] = set()
    for canonical, aliases in alias_lookup.items():
        for alias in aliases:
            pattern = _alias_to_regex(alias)
            if pattern.search(text):
                found.add(canonical)
                break  # one alias hit is enough for this skill

    return sorted(found)


def normalize_skill_name(raw_skill: str) -> str:
    """
    Map a free-typed / raw skill string to its canonical dictionary name,
    if a match exists. Otherwise return the trimmed original (title-cased)
    so custom skills (not yet in the dictionary) can still be stored.
    """
    skill_dict = load_skill_dictionary()
    raw_lower = raw_skill.strip().lower()

    for canonical, meta in skill_dict.items():
        aliases = [a.lower() for a in meta.get("aliases", [])] + [canonical.lower()]
        if raw_lower in aliases:
            return canonical

    return raw_skill.strip()


def get_all_known_skills() -> List[str]:
    """Return every canonical skill name in the dictionary, sorted alphabetically."""
    return sorted(load_skill_dictionary().keys())


def get_skill_category(skill_name: str) -> str:
    skill_dict = load_skill_dictionary()
    return skill_dict.get(skill_name, {}).get("category", "General")
