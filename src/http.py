"""Shared HTTP helper (stdlib only, so the cron job has no pip dependencies)."""
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def get(url: str, timeout: int = 25, retries: int = 2, delay: float = 1.0) -> bytes:
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - keep the run alive
            last = exc
            time.sleep(delay)
    raise RuntimeError(f"GET failed after {retries + 1} attempts: {url} ({last})")
