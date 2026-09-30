"""Company career boards with public JSON APIs (no auth):
  - Greenhouse: https://boards-api.greenhouse.io/v1/boards/{token}/jobs
  - Ashby:      https://api.ashbyhq.com/posting-api/job-board/{token}

Board tokens live in config.yaml and must be verified working before adding.
Greenhouse listings carry no posted date, so first-seen date is used.
"""
import json
import time

from .. import http
from ..filters import is_me_intern


def _greenhouse_job(board: str, job: dict, today: str) -> dict | None:
    title = (job.get("title") or "").strip()
    if not is_me_intern(title):
        return None
    loc = job.get("location") or {}
    return {
        "id": f"greenhouse:{board}:{job.get('id')}",
        "source": "greenhouse",
        "company": board.replace("-", " ").title(),
        "title": title,
        "location": loc.get("name", ""),
        "url": job.get("absolute_url") or "",
        "date_posted": today,  # boards API exposes no posted date; first-seen
        "date_approx": True,
    }


def _ashby_job(board: str, job: dict, today: str) -> dict | None:
    title = (job.get("title") or "").strip()
    if not is_me_intern(title):
        return None
    return {
        "id": f"ashby:{board}:{job.get('id')}",
        "source": "ashby",
        "company": board.replace("-", " ").title(),
        "title": title,
        "location": job.get("locationName") or "",
        "url": job.get("jobUrl") or "",
        "date_posted": today,  # posting API exposes no posted date; first-seen
        "date_approx": True,
    }


def fetch(cfg: dict) -> list[dict]:
    today = time.strftime("%Y-%m-%d", time.gmtime())
    out: list[dict] = []
    for board in cfg["ats"]["greenhouse_boards"]:
        try:
            raw = http.get(
                f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                timeout=cfg["run"]["request_timeout"],
            )
            for job in json.loads(raw.decode("utf-8")).get("jobs", []):
                rec = _greenhouse_job(board, job, today)
                if rec:
                    rec["company"] = _company_name(board, job)
                    out.append(rec)
        except Exception as exc:  # noqa: BLE001 - one bad board must not kill the run
            print(f"[ats] greenhouse board '{board}' failed: {exc}")
    for board in cfg["ats"]["ashby_boards"]:
        try:
            raw = http.get(
                f"https://api.ashbyhq.com/posting-api/job-board/{board}",
                timeout=cfg["run"]["request_timeout"],
            )
            payload = json.loads(raw.decode("utf-8"))
            for job in payload.get("jobs", []):
                rec = _ashby_job(board, job, today)
                if rec:
                    rec["company"] = payload.get("name") or rec["company"]
                    out.append(rec)
        except Exception as exc:  # noqa: BLE001
            print(f"[ats] ashby board '{board}' failed: {exc}")
    return out


def _company_name(board: str, job: dict) -> str:
    # Greenhouse job payloads don't include the company display name; the
    # metadata endpoint does, but the board token is usually the name already.
    return board.replace("-", " ").title()
