"""Build the daily HTML email. Inline CSS only — Gmail strips <style> blocks."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from .sources import LOGIN_ONLY, Project

NAMES = {"freelancer": "Freelancer", "truelancer": "Truelancer", "workana": "Workana",
         "samsstc": "SAMS-STC", "tendernews": "TenderNews",
         "liceum": "Liceum", "opentrain": "OpenTrain"}

INK, MUTED, LINE, LINK = "#1f2328", "#656d76", "#d8dee4", "#0969da"


def _age(p: Project, now: datetime) -> str:
    if p.posted is None:
        return ""
    if p.date_only:
        return p.posted.strftime("%d %b")
    mins = int((now - p.posted).total_seconds() // 60)
    return f"{mins} min ago" if mins < 60 else f"{mins // 60} h ago"


def _row(p: Project, now: datetime) -> str:
    meta = " · ".join(x for x in [_age(p, now), p.budget] if x)
    summary = p.summary[:220] + ("…" if len(p.summary) > 220 else "")
    return (
        f'<div style="padding:12px 0;border-top:1px solid {LINE};">'
        f'<a href="{html.escape(p.url)}" style="color:{LINK};font-size:15px;'
        f'font-weight:600;text-decoration:none;">{html.escape(p.title)}</a>'
        f'<div style="color:{MUTED};font-size:12px;margin-top:3px;">{html.escape(meta)}</div>'
        + (f'<div style="color:{INK};font-size:13px;line-height:1.5;margin-top:5px;">'
           f'{html.escape(summary)}</div>' if summary else "")
        + "</div>")


def build(projects: list[Project], report: dict[str, str], hours: float
          ) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    today = datetime.now().strftime("%d %b %Y")
    n = len(projects)
    subject = (f"{n} new annotation project{'s' if n != 1 else ''} — {today}"
               if n else f"No new annotation projects — {today}")

    sections = []
    for source in NAMES:
        mine = sorted((p for p in projects if p.source == source),
                      key=lambda p: p.posted or now, reverse=True)
        if mine:
            sections.append(
                f'<div style="margin-top:22px;color:{INK};font-size:16px;font-weight:700;">'
                f'{NAMES[source]} <span style="color:{MUTED};font-weight:400;">'
                f'({len(mine)})</span></div>' + "".join(_row(p, now) for p in mine))
    if not sections:
        sections.append(
            f'<div style="margin-top:18px;padding:16px;border:1px solid {LINE};'
            f'border-radius:8px;color:{MUTED};font-size:14px;">Nothing new matched in '
            f'the last {hours:g} hours. This mail confirms the check ran.</div>')

    status = "".join(
        f'<tr><td style="padding:3px 14px 3px 0;color:{INK};">{NAMES.get(s, s)}</td>'
        f'<td style="padding:3px 0;color:{"#cf222e" if line.startswith("failed") else MUTED};">'
        f'{html.escape(line)}</td></tr>' for s, line in report.items())
    status += "".join(
        f'<tr><td style="padding:3px 14px 3px 0;color:{INK};">{NAMES[s]}</td>'
        f'<td style="padding:3px 0;color:{MUTED};">not checked: projects are only '
        f'visible after login — <a href="{url}" style="color:{LINK};">open site</a></td></tr>'
        for s, url in LOGIN_ONLY.items())

    doc = f"""<!doctype html><html><body style="margin:0;padding:20px;background:#ffffff;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:640px;margin:0 auto;">
  <div style="color:{INK};font-size:21px;font-weight:800;">Annotation projects</div>
  <div style="color:{MUTED};font-size:13px;margin-top:5px;">
    {today} · posted in the last {hours:g} hours · {n} new</div>
  {"".join(sections)}
  <div style="margin-top:26px;padding-top:12px;border-top:1px solid {LINE};
       color:{MUTED};font-size:12px;font-weight:700;">Sites checked</div>
  <table style="border-collapse:collapse;font-size:12px;margin-top:4px;">{status}</table>
</div></body></html>"""
    return subject, doc


def write(doc: str, path: str | Path = "out/digest.html") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")
    return path
