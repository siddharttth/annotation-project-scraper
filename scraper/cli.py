"""annotation-project-scraper CLI: fetch -> filter -> digest -> mail."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import digest, mailer
from .select import Seen, is_fresh, on_topic
from .sources import fetch_all


def _load_env(path: str = ".env") -> None:
    """Minimal .env reader so there is no python-dotenv dependency."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cmd_run(args) -> int:
    p = Path(args.config)
    if not p.exists():
        raise SystemExit(f"config not found: {p}  (run from the project root)")
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    hours = float(args.hours or cfg.get("fresh_hours", 24))
    seen = Seen(cfg.get("seen_file", "seen.json"))

    print("[1/3] reading sites")
    projects, report = fetch_all(cfg.get("search_terms") or ["data annotation"],
                                 only=cfg.get("sources"))
    listed = len(projects)

    print("[2/3] filtering")
    now = datetime.now(timezone.utc)
    relevant = [x for x in projects
                if on_topic(x, cfg.get("keywords") or [], cfg.get("exclude") or [])]
    fresh = [x for x in relevant if is_fresh(x, now, hours)]
    new = seen.unseen(fresh)
    print(f"  {listed} listed -> {len(relevant)} on topic -> "
          f"{len(fresh)} in the last {hours:g}h -> {len(new)} not sent before")

    print("[3/3] digest")
    subject, doc = digest.build(new, report, hours)
    print(f"  wrote {digest.write(doc, cfg.get('digest_file', 'out/digest.html'))}")
    for x in new:
        print(f"  + [{x.source}] {x.title[:70]}  {x.url}")

    if not args.send:
        print("  --send not passed, email skipped")
        return 0
    try:
        mailer.send(subject, doc)
    except Exception as e:  # bad app password, blocked port, offline
        print(f"  ! email failed ({type(e).__name__}: {e}) — digest still on disk")
        return 1
    # Recorded only once mailed, so a failed send is retried by the next run.
    seen.record(new)
    return 0


def main(argv=None) -> int:
    _load_env()
    ap = argparse.ArgumentParser(
        prog="scraper", description="Daily digest of fresh annotation projects.")
    ap.add_argument("--config", default="config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="read the sites and build the digest")
    run.add_argument("--send", action="store_true", help="email the digest")
    run.add_argument("--hours", type=float, help="freshness window (default: config)")
    run.set_defaults(func=cmd_run)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
