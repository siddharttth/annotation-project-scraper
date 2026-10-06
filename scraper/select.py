"""Decide which listings go in the mail: on-topic, fresh, and not sent before."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .sources import Project


def on_topic(p: Project, keywords: list[str], exclude: list[str]) -> bool:
    """Title or summary matches a keyword and no exclude pattern.

    The sites' own searches are loose ("data annotation" returns bridge tenders
    and photo shoots), so every source goes through the same gate.
    """
    blob = f"{p.title} {p.summary}"
    if not any(re.search(k, blob, re.I) for k in keywords or [r"."]):
        return False
    return not any(re.search(x, blob, re.I) for x in exclude or [])


def is_fresh(p: Project, now: datetime, hours: float) -> bool:
    """Posted within the window. An undated listing is not fresh."""
    if p.posted is None:
        return False
    if p.date_only:
        # A day with no time: "within 24 hours" means today or yesterday.
        return p.posted.date() >= (now - timedelta(hours=hours)).date()
    return p.posted >= now - timedelta(hours=hours)


class Seen:
    """Keys already mailed, so a late or repeated run never sends one twice."""

    KEEP_DAYS = 45

    def __init__(self, path: str | Path = "seen.json"):
        self.path = Path(path)
        self.data: dict[str, str] = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                print(f"  ! {self.path} corrupt, starting fresh")

    def unseen(self, projects: list[Project]) -> list[Project]:
        return [p for p in projects if p.key not in self.data]

    def record(self, projects: list[Project]) -> None:
        now = datetime.now(timezone.utc)
        for p in projects:
            self.data.setdefault(p.key, now.isoformat(timespec="seconds"))
        cutoff = (now - timedelta(days=self.KEEP_DAYS)).isoformat(timespec="seconds")
        self.data = {k: v for k, v in self.data.items() if v >= cutoff}
        self.path.write_text(json.dumps(self.data, indent=2))
