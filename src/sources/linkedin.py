"""LinkedIn Jobs via the public guest search API (no login required).

Endpoint: https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
Returns HTML job cards; we parse title / company / location / posted date.
"""
import re
import time
import urllib.parse
import html as html_lib

from .. import http
from ..filters import is_me_intern

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

TITLE_RE = re.compile(r'base-search-card__title[^>]*>(.*?)</h3>', re.S)
COMPANY_RE = re.compile(r'base-search-card__subtitle[^>]*>(.*?)</h4>', re.S)
LOCATION_RE = re.compile(r'job-search-card__location[^>]*>(.*?)</span>', re.S)
DATE_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
URN_RE = re.compile(r'urn:li:jobPosting:(\d+)')
TAG_RE = re.compile(r'<[^>]+>')


def _clean(fragment: str | None) -> str:
    if not fragment:
        return ""
    text = TAG_RE.sub(" ", fragment)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_cards(html: str) -> list[dict]:
    jobs = []
    for card in re.findall(r"<li>(.*?)</li>", html, re.S):
        urn = URN_RE.search(card)
        if not urn:
            continue
        jid = urn.group(1)
        title = _clean(TITLE_RE.search(card).group(1) if TITLE_RE.search(card) else "")
        company = _clean(COMPANY_RE.search(card).group(1) if COMPANY_RE.search(card) else "")
        location = _clean(LOCATION_RE.search(card).group(1) if LOCATION_RE.search(card) else "")
        date_m = DATE_RE.search(card)
        date_posted = date_m.group(1)[:10] if date_m else ""
        if not title:
            continue
        jobs.append({
            "id": f"linkedin:{jid}",
            "source": "linkedin",
            "company": company,
            "title": title,
            "location": location,
            "url": f"https://www.linkedin.com/jobs/view/{jid}",
            "date_posted": date_posted,
        })
    return jobs


def fetch(cfg: dict) -> list[dict]:
    li = cfg["linkedin"]
    out: list[dict] = []
    for query in li["queries"]:
        for page in range(li["max_pages_per_query"]):
            params = {
                "keywords": query,
                "location": cfg["run"]["location"],
                "f_TPR": li["posted_within"],
                "start": page * 10,
            }
            if li.get("internship_level_only"):
                params["f_E"] = "1"  # internship experience level
            url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
            html = http.get(url, timeout=cfg["run"]["request_timeout"]).decode("utf-8", "replace")
            cards = _parse_cards(html)
            if not cards:
                break  # no more pages for this query
            for job in cards:
                if is_me_intern(job["title"]):
                    out.append(job)
            time.sleep(cfg["run"]["polite_delay_seconds"])
    # dedupe within source (same posting can surface under several queries)
    seen, uniq = set(), []
    for job in out:
        if job["id"] not in seen:
            seen.add(job["id"])
            uniq.append(job)
    return uniq
