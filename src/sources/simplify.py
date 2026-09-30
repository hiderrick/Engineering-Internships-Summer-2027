"""SimplifyJobs repo feed: the public listings.json published by the
SimplifyJobs/Summer2027-Internships repo (no auth, no scraping needed).

Each entry carries title, company, locations, url, date_posted (unix) and an
active flag maintained by the repo's automation.
"""
import json
import time

from .. import http
from ..filters import is_me_intern


def fetch(cfg: dict) -> list[dict]:
    url = cfg["simplify_repo"]["listings_url"]
    raw = http.get(url, timeout=cfg["run"]["request_timeout"])
    listings = json.loads(raw.decode("utf-8"))
    cutoff = time.time() - cfg["run"]["lookback_days"] * 86400

    out = []
    for item in listings:
        if not (item.get("active") and item.get("is_visible", True)):
            continue
        if item.get("date_posted", 0) < cutoff:
            continue
        title = (item.get("title") or "").strip()
        if not is_me_intern(title):
            continue
        locations = item.get("locations") or []
        out.append({
            "id": f"simplify:{item.get('id')}",
            "source": "simplify",
            "company": (item.get("company_name") or "").strip(),
            "title": title,
            "location": "; ".join(locations),
            "url": item.get("url") or "",
            "date_posted": time.strftime("%Y-%m-%d", time.gmtime(item["date_posted"])),
            "term": ", ".join(item.get("terms") or []),
        })
    return out
