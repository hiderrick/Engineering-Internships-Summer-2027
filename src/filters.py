"""Mechanical-engineering relevance filter for job titles."""
import re

# A posting must match at least one INCLUDE pattern AND at least one INTERN
# pattern, and must NOT match any EXCLUDE pattern.
INCLUDE = [
    r"mechanical", r"mechatronic\w*", r"robotic\w*",
    r"manufacturing", r"aerospace", r"aeronautical", r"astronautical",
    r"design engineer\b", r"hardware engineer\b", r"thermal", r"\bhvac\b",
    r"automotive", r"biomechanic\w*", r"product design",
    r"\bstructures?\b", r"structural", r"propulsion", r"aerodynamic\w*",
    r"test engineer\b", r"systems engineer\b", r"reliability engineer\b",
    r"quality engineer\b", r"process engineer\b", r"industrial engineer\b",
    r"materials? engineer\b", r"metrology", r"tooling",
    r"\bcad\b", r"\bfea\b", r"solidworks", r"catia", r"ansys", r"gd&t",
    r"controls engineer\b", r"\bdynamics\b", r"vibration", r"fluid",
    r"combustion", r"turbomachinery", r"\buav\b", r"drone", r"spacecraft",
]

INTERN = [
    r"\binterns?\b", r"\binternships?\b", r"\bco-?ops?\b", r"\bco op\b",
]

EXCLUDE = [
    r"software", r"firmware", r"data scientist", r"data analyst",
    r"data engineer", r"machine learning", r"artificial intelligence",
    r"electrical engineer", r"\belectrical\b", r"electronic", r"\brtl\b", r"\basic\b",
    r"\bcivil\b", r"chemical",
    r"\bsales\b", r"marketing", r"finance", r"accounting",
    r"human resources", r"recruiter", r"\blegal\b",
    r"product manager", r"program manager", r"project manager",
    r"supply chain", r"technician", r"customer success",
    r"technical writer", r"nurse", r"solutions architect",
    r"embedded", r"devops", r"frontend", r"front-end", r"backend",
    r"back-end", r"full.?stack", r"\bios\b", r"android",
]

_INCLUDE_RE = [re.compile(p, re.I) for p in INCLUDE]
_INTERN_RE = [re.compile(p, re.I) for p in INTERN]
_EXCLUDE_RE = [re.compile(p, re.I) for p in EXCLUDE]


def is_me_intern(title: str, extra_text: str = "") -> bool:
    """True when the posting looks like a mechanical-engineering (or closely
    related) internship/co-op."""
    blob = f"{title} {extra_text}"
    if not any(rx.search(blob) for rx in _INTERN_RE):
        return False
    if not any(rx.search(blob) for rx in _INCLUDE_RE):
        return False
    if any(rx.search(blob) for rx in _EXCLUDE_RE):
        return False
    return True
