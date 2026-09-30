#!/usr/bin/env python3
"""ME Internship Tracker - twice-daily collector.

Fetches new mechanical-engineering (and closely related) internship postings
from all configured sources, dedupes against state.json, appends to
output/jobs.json, and renders output/README.md in the style of the
SimplifyJobs internship repos (Company | Role | Location | Application | Date Posted).

Usage:
    python3 run.py              # normal run (writes state + output)
    python3 run.py --dry-run    # fetch + print stats only, write nothing
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.sources import linkedin, simplify, ats  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))


def load_config() -> dict:
    import yaml  # type: ignore
    with open(os.path.join(BASE, "config.yaml")) as fh:
        return yaml.safe_load(fh)


def load_config_no_yaml() -> dict:
    """Fallback tiny YAML reader: config.yaml uses only simple scalars/lists."""
    cfg: dict = {}
    stack: list[tuple[int, dict | list, str | None]] = [(0, cfg, None)]
    current_list_key = None
    with open(os.path.join(BASE, "config.yaml")) as fh:
        for raw in fh:
            if not raw.strip() or raw.strip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            line = raw.strip()
            while stack and indent < stack[-1][0]:
                stack.pop()
            parent = stack[-1][1]
            if line.startswith("- "):
                val = line[2:].strip().strip('"')
                if isinstance(parent, list):
                    parent.append(_coerce(val))
                continue
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip().strip('"')
            if val == "":
                # nested block; peek next non-empty line to decide dict vs list
                node: dict | list = {}
                parent[key] = node
                stack.append((indent + 2, node, key))
            else:
                if isinstance(parent, list):
                    parent.append(_coerce(val))
                else:
                    parent[key] = _coerce(val)
    # fix: turn dicts that only got list items into lists (heuristic: empty dicts under list parents)
    return _fix_lists(cfg)


def _coerce(val: str):
    if val.lower() in ("true", "false"):
        return val.lower() == "true"
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _fix_lists(node):
    # Our config nests lists as `key:` followed by `- item` lines; the naive
    # parser above creates a dict for the key. Detect dicts whose children were
    # appended as list items under a numeric-ish scheme is overkill; instead we
    # parse lists with a dedicated pass below.
    return node


def parse_config() -> dict:
    """Minimal YAML parser sufficient for our config shape."""
    cfg: dict = {"run": {}, "linkedin": {"queries": []}, "simplify_repo": {},
                 "ats": {"greenhouse_boards": [], "ashby_boards": []}, "output": {}}
    section = None
    list_key = None
    with open(os.path.join(BASE, "config.yaml")) as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            s = line.strip()
            if indent == 0 and s.endswith(":"):
                section = s[:-1]
                list_key = None
                continue
            if s.startswith("- "):
                if section and list_key:
                    cfg[section][list_key].append(_coerce(s[2:].strip().strip('"')))
                continue
            if indent == 2:
                key, _, val = s.partition(":")
                key, val = key.strip(), val.strip().strip('"')
                val = re.sub(r"\s+#.*$", "", val).strip()  # strip inline comments
                if val == "":
                    list_key = key
                    cfg[section][key] = []
                else:
                    cfg[section][key] = _coerce(val)
                    list_key = None
    return cfg


def norm_key(job: dict) -> str:
    return "|".join(re.sub(r"\s+", " ", (job.get(k) or "").lower()).strip()
                   for k in ("company", "title", "location"))


def esc(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def render_readme(jobs: list[dict], new_count: int, run_ts: str) -> str:
    lines = [
        "# Mechanical Engineering Internships",
        "",
        "Auto-updated twice daily. Mechanical engineering internships and closely",
        "related roles (robotics, manufacturing, aerospace, design/hardware, thermal, etc.).",
        "",
        f"_Last updated: {run_ts} UTC — {len(jobs)} active postings"
        + (f", {new_count} new this run." if new_count else ".") + "_",
        "",
        "| Company | Role | Location | Application | Date Posted |",
        "| ------- | ---- | -------- | ----------- | ----------- |",
    ]
    for j in jobs:
        link = f"[Apply]({j['url']})" if j.get("url") else ""
        lines.append(f"| {esc(j.get('company'))} | {esc(j.get('title'))} | "
                     f"{esc(j.get('location'))} | {link} | {j.get('date_posted', '')} |")
    lines += ["",
              "_Sources: LinkedIn Jobs, SimplifyJobs repo feed, company career boards (Greenhouse/Ashby)._",
              "_Dates on company-board postings are first-seen dates — those boards don't publish posted dates._"]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = parse_config()
    out_dir = os.path.join(BASE, cfg["output"]["dir"])
    os.makedirs(out_dir, exist_ok=True)
    state_path = os.path.join(BASE, "state.json")
    jobs_path = os.path.join(out_dir, cfg["output"]["jobs_name"])
    readme_path = os.path.join(out_dir, cfg["output"]["readme_name"])

    state = {"seen_ids": []}
    if os.path.exists(state_path):
        state = json.load(open(state_path))
    seen_ids = set(state.get("seen_ids", []))

    prior_jobs: dict[str, dict] = {}
    if os.path.exists(jobs_path):
        for j in json.load(open(jobs_path)):
            prior_jobs[j["id"]] = j

    run_ts = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
    all_new, stats = [], {}
    sources = []
    if cfg["linkedin"].get("enabled"):
        sources.append(("linkedin", linkedin.fetch))
    if cfg["simplify_repo"].get("enabled"):
        sources.append(("simplify", simplify.fetch))
    if cfg["ats"].get("enabled"):
        sources.append(("ats", ats.fetch))

    for name, fn in sources:
        try:
            jobs = fn(cfg)
            stats[name] = len(jobs)
            all_new.extend(jobs)
        except Exception as exc:  # noqa: BLE001 - keep the run alive
            stats[name] = f"ERROR: {exc}"
            print(f"[{name}] failed: {exc}", file=sys.stderr)

    # cross-source dedupe by normalized (company, title, location)
    uniq: dict[str, dict] = {}
    for job in all_new:
        k = norm_key(job)
        if k not in uniq:
            uniq[k] = job
    fresh = [j for j in uniq.values() if j["id"] not in seen_ids and j["id"] not in prior_jobs]

    print(f"run {run_ts} UTC")
    for name, val in stats.items():
        print(f"  {name}: {val} matching postings")
    print(f"  new postings this run: {len(fresh)}")

    if args.dry_run:
        for j in fresh[:20]:
            print(f"  + [{j['date_posted']}] {j['company']} — {j['title']} ({j['location']})")
        return 0

    for j in fresh:
        j.setdefault("first_seen", run_ts[:10])
        prior_jobs[j["id"]] = j
    jobs = sorted(prior_jobs.values(),
                  key=lambda j: (j.get("date_posted") or "", j.get("company") or ""),
                  reverse=True)

    with open(jobs_path, "w") as fh:
        json.dump(jobs, fh, indent=1)
    with open(readme_path, "w") as fh:
        fh.write(render_readme(jobs, len(fresh), run_ts))
    state["seen_ids"] = sorted(seen_ids | {j["id"] for j in uniq.values()})
    with open(state_path, "w") as fh:
        json.dump(state, fh)
    with open(os.path.join(out_dir, "runs.log"), "a") as fh:
        fh.write(f"{run_ts} UTC | sources={stats} | new={len(fresh)} | total={len(jobs)}\n")

    print(f"wrote {len(jobs)} jobs -> {jobs_path}")
    print(f"wrote README -> {readme_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
