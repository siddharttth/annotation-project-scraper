"""Read public project listings. One pure parser per site, HTTP kept separate.

Each `parse_*` takes an already-fetched body and returns list[Project], so the
tests run on fixtures with no network. Only public listing pages and public
APIs are read, once a day; nothing behind a login is touched.
"""
from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote_plus

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en",
}
TIMEOUT = 30

_BLOCK = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def text(raw: str | None) -> str:
    """HTML fragment -> one line of plain text."""
    if not raw:
        return ""
    return " ".join(html.unescape(_TAG.sub(" ", _BLOCK.sub(" ", raw))).split())


@dataclass
class Project:
    source: str
    id: str
    title: str
    url: str
    posted: datetime | None = None   # UTC. None means the site gave no usable date.
    date_only: bool = False          # the site gives a day, not a time
    budget: str = ""
    summary: str = ""

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"


# ---------------------------------------------------------------- freelancer --

def parse_freelancer(body: Any, now: datetime | None = None) -> list[Project]:
    out = []
    for p in ((body or {}).get("result") or {}).get("projects") or []:
        budget = p.get("budget") or {}
        code = (p.get("currency") or {}).get("code") or ""
        lo, hi = budget.get("minimum"), budget.get("maximum")
        money = " - ".join(f"{v:g}" for v in (lo, hi) if v is not None)
        ts = p.get("time_submitted")
        out.append(Project(
            source="freelancer",
            id=str(p.get("id")),
            title=(p.get("title") or "").strip(),
            url=f"https://www.freelancer.com/projects/{p.get('seo_url') or p.get('id')}",
            posted=datetime.fromtimestamp(ts, timezone.utc) if ts else None,
            budget=f"{code} {money}{' / hour' if p.get('type') == 'hourly' else ''}".strip()
            if money else "",
            summary=(p.get("preview_description") or p.get("description") or "").strip(),
        ))
    return out


# ---------------------------------------------------------------- truelancer --

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def parse_truelancer(page: str, now: datetime | None = None) -> list[Project]:
    """The listing page, which embeds the same rows the API returns."""
    m = _NEXT_DATA.search(page or "")
    if not m:
        raise ValueError("truelancer: listing data not found in page")
    data = json.loads(m.group(1))
    return parse_truelancer_api(((data.get("props") or {}).get("pageProps") or {})
                                .get("data") or {})


def parse_truelancer_api(body: Any, now: datetime | None = None) -> list[Project]:
    rows = ((body or {}).get("projects") or {}).get("data") or []
    out = []
    for p in rows:
        posted = None
        if p.get("created_at"):
            posted = datetime.fromisoformat(str(p["created_at"]).replace("Z", "+00:00"))
        budget = p.get("budget")
        out.append(Project(
            source="truelancer",
            id=str(p.get("id")),
            title=(p.get("title") or "").strip(),
            url=p.get("link") or "https://www.truelancer.com/freelance-jobs",
            posted=posted,
            budget=f"{p.get('currency') or ''} {budget}".strip() if budget else "",
            summary=text(p.get("description")),
        ))
    return out


# ------------------------------------------------------------------- workana --

_WORKANA = re.compile(r":results-initials='(.*?)'", re.S)
_AGO = re.compile(r"(\d+|an?)\s+(minute|hour|day|week|month|year)s?\s+ago", re.I)
_UNIT = {"minute": timedelta(minutes=1), "hour": timedelta(hours=1),
         "day": timedelta(days=1), "week": timedelta(weeks=1),
         "month": timedelta(days=30), "year": timedelta(days=365)}


def relative_date(label: str, now: datetime) -> datetime | None:
    """"3 hours ago" / "Yesterday" / "Last month" -> an approximate UTC time."""
    s = (label or "").strip().lower()
    if not s:
        return None
    if "just now" in s or "moment" in s or s == "today":
        return now
    if s == "yesterday":
        return now - timedelta(days=1)
    m = _AGO.search(s)
    if m:
        n = 1 if m.group(1).startswith("a") else int(m.group(1))
        return now - n * _UNIT[m.group(2).lower()]
    m = re.match(r"last (week|month|year)", s)
    if m:
        return now - _UNIT[m.group(1)]
    return None


def parse_workana(page: str, now: datetime | None = None) -> list[Project]:
    now = now or datetime.now(timezone.utc)
    m = _WORKANA.search(page or "")
    if not m:
        raise ValueError("workana: listing data not found in page")
    data = json.loads(html.unescape(m.group(1)))
    out = []
    for r in data.get("results") or []:
        href = re.search(r'href="([^"]+)"', r.get("title") or "")
        out.append(Project(
            source="workana",
            id=str(r.get("slug")),
            title=text(r.get("title")),
            url=f"https://www.workana.com{href.group(1)}" if href
            else "https://www.workana.com/jobs",
            posted=relative_date(r.get("postedDate") or "", now),
            budget=text(str(r.get("budget") or "")),
            summary=text(r.get("description")),
        ))
    return out


# ------------------------------------------------------------------ sams-stc --

_SAMS_LINK = re.compile(
    r'<a class="rfp-view" href="(/rfp-tender/rfp-tender-description/([^/"]+)/(\d+))"')
_SAMS_ISSUED = re.compile(r"Issued\s+([A-Za-z]{3} \d{1,2}, \d{4})")
_SAMS_TITLE = re.compile(r"·\s*(?:Live|Closing Soon|New|Open)\s*·\s*(.+?)\s+Closes\b")


def parse_samsstc(page: str, now: datetime | None = None) -> list[Project]:
    out, start = [], 0
    for m in _SAMS_LINK.finditer(page or ""):
        card = text(page[start:m.start()])
        start = m.end()
        title = _SAMS_TITLE.findall(card)
        issued = _SAMS_ISSUED.findall(card)
        posted = None
        if issued:
            posted = datetime.strptime(issued[-1], "%b %d, %Y").replace(tzinfo=timezone.utc)
        out.append(Project(
            source="samsstc",
            id=m.group(3),
            # The slug is the fallback: it is the title, lower-cased and hyphenated.
            title=title[-1] if title else m.group(2).replace("-", " ").capitalize(),
            url=f"https://www.samsstc.com{m.group(1)}",
            posted=posted,
            date_only=True,
        ))
    return out


# ---------------------------------------------------------------- tendernews --

_TENDER_ROW = re.compile(
    r'<tr>\s*<td class="hide">(\d+)</td>\s*<td>([^<]+)</td>\s*<td>([^<]*)</td>\s*'
    r'<td>([^<]*)</td>\s*<td class="hide">([^<]*)</td>\s*<td>(.*?)<a[^>]*href=\'([^\']+)\'',
    re.S)


def parse_tendernews(page: str, now: datetime | None = None) -> list[Project]:
    out = []
    for ref, posted, deadline, location, value, desc, href in _TENDER_ROW.findall(page or ""):
        try:
            when = datetime.strptime(posted.strip(), "%d-%b-%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            when = None
        out.append(Project(
            source="tendernews",
            id=ref,
            title=text(desc),
            url=html.unescape(href),
            posted=when,
            date_only=True,
            budget="" if "refer" in value.lower() else value.strip(),
            summary=f"{location.strip()} · deadline {deadline.strip()}",
        ))
    return out


# ------------------------------------------------------------------- fetching --

RETRY_STATUS = (429, 500, 502, 503)
RETRY_WAITS = (5, 20)   # seconds between attempts


def _get(url: str, session: requests.Session) -> requests.Response:
    for wait in (*RETRY_WAITS, None):
        r = session.get(url, headers=UA, timeout=TIMEOUT)
        if r.status_code not in RETRY_STATUS or wait is None:
            break
        time.sleep(wait)
    if r.status_code != 200:
        raise ValueError(f"HTTP {r.status_code}")
    return r


def _freelancer_urls(queries: list[str]) -> list[str]:
    return ["https://www.freelancer.com/api/projects/0.1/projects/active/"
            f"?query={quote_plus(q)}&limit=50&sort_field=time_submitted" for q in queries]


def _workana_urls(queries: list[str]) -> list[str]:
    return [f"https://www.workana.com/jobs?language=en&query={quote_plus(q)}" for q in queries]


# name -> (urls for these search terms, parser, body is JSON?)
SOURCES: dict[str, tuple[Callable[[list[str]], list[str]], Callable, bool]] = {
    "freelancer": (_freelancer_urls, parse_freelancer, True),
    "truelancer": (lambda q: ["https://api.truelancer.com/api/v1/projects"
                              "?skillName=ai-data-annotation&listType=skill&page=1"],
                   parse_truelancer_api, True),
    "workana": (_workana_urls, parse_workana, False),
    "samsstc": (lambda q: ["https://www.samsstc.com/rfp-tender/rfp-list"],
                parse_samsstc, False),
    "tendernews": (lambda q: ["https://www.tendernews.com/tenders/latest-tender/"
                              "ai-data-annotation.html"], parse_tendernews, False),
}

# Tried when the primary read of a source fails. Truelancer rate-limits its
# API by address (HTTP 429 from cloud runners); the page carries the same rows.
FALLBACK: dict[str, tuple[Callable[[list[str]], list[str]], Callable, bool]] = {
    "truelancer": (lambda q: ["https://www.truelancer.com/freelance-ai-data-annotation-jobs"],
                   parse_truelancer, False),
}

# Listed by the user, but projects are only visible after signing in, so there
# is no public page to read. Reported in every digest instead of silently skipped.
LOGIN_ONLY = {
    "liceum": "https://liceum.ai/",
    "opentrain": "https://www.opentrain.ai/",
}


def fetch_all(queries: list[str], only: list[str] | None = None
              ) -> tuple[list[Project], dict[str, str]]:
    """Every source, never raising. Returns (projects, {source: status line})."""
    now = datetime.now(timezone.utc)
    session = requests.Session()
    projects: list[Project] = []
    report: dict[str, str] = {}
    for name, primary in SOURCES.items():
        if only and name not in only:
            continue
        found: dict[str, Project] = {}
        for urls, parser, is_json in filter(None, (primary, FALLBACK.get(name))):
            try:
                for url in urls(queries):
                    r = _get(url, session)
                    for p in parser(r.json() if is_json else r.text, now):
                        found.setdefault(p.key, p)
                report[name] = f"{len(found)} listed"
                break
            except Exception as e:  # site down, layout changed, blocked
                report[name] = f"failed ({type(e).__name__}: {str(e)[:80]})"
        projects.extend(found.values())
        print(f"  {name:<11} {report[name]}")
    return projects, report
