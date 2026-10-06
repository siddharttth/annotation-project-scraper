"""Parsers and the selection gate, on fixtures in each site's own shape.

No network. Fixture dates are relative to *now*, never hardcoded, so they
cannot silently age out of the freshness window.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper import digest
from scraper.select import Seen, is_fresh, on_topic
from scraper.sources import (Project, parse_freelancer, parse_samsstc, parse_tendernews,
                             parse_truelancer, parse_workana, relative_date)

NOW = datetime.now(timezone.utc)
KEYWORDS = ["annotat", r"label(l)?ing"]


def test_freelancer_maps_epoch_seconds_budget_and_url():
    body = {"result": {"projects": [{
        "id": 7, "title": " Video Annotation ", "seo_url": "video/Video-Annotation",
        "time_submitted": int((NOW - timedelta(hours=3)).timestamp()), "type": "hourly",
        "currency": {"code": "USD"}, "budget": {"minimum": 2.0, "maximum": 8.0},
        "preview_description": "Draw boxes"}]}}
    (p,) = parse_freelancer(body)

    assert (p.key, p.title, p.budget) == ("freelancer:7", "Video Annotation", "USD 2 - 8 / hour")
    assert p.url == "https://www.freelancer.com/projects/video/Video-Annotation"
    assert is_fresh(p, NOW, 24) and not is_fresh(p, NOW, 2)


def test_truelancer_reads_the_embedded_page_data():
    data = {"props": {"pageProps": {"data": {"projects": {"data": [{
        "id": 9, "title": "MRI Annotation", "created_at": "2026-08-20T16:48:55.000000Z",
        "link": "https://www.truelancer.com/freelance-project/mri-9",
        "description": "<p>Label &amp; review</p>"}]}}}}}
    page = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    (p,) = parse_truelancer(page)

    assert p.summary == "Label & review"
    assert p.posted == datetime(2026, 8, 20, 16, 48, 55, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        parse_truelancer("<html>layout changed</html>")


def test_workana_turns_relative_labels_into_dates():
    data = {"results": [
        {"slug": "a", "title": '<a href="/job/a"><span>Image Labeling</span></a>',
         "postedDate": "3 hours ago", "budget": "USD 100 - 250", "description": "x"},
        {"slug": "b", "title": '<a href="/job/b">Old one</a>', "postedDate": "Last month"}]}
    page = f"<search :results-initials='{html.escape(json.dumps(data))}'></search>"
    new, old = parse_workana(page, NOW)

    assert (new.title, new.url) == ("Image Labeling", "https://www.workana.com/job/a")
    assert is_fresh(new, NOW, 24) and not is_fresh(old, NOW, 24)


@pytest.mark.parametrize("label,expected", [
    ("Just now", timedelta(0)), ("an hour ago", timedelta(hours=1)),
    ("Yesterday", timedelta(days=1)), ("2 weeks ago", timedelta(weeks=2)),
])
def test_relative_date(label, expected):
    assert relative_date(label, NOW) == NOW - expected
    assert relative_date("sometime", NOW) is None


def test_samsstc_reads_title_issue_date_and_link_per_card():
    issued = NOW.strftime("%b %d, %Y")
    page = f"""
      <div><span>Procurement of Services</span> · <span>Live</span> ·
        <h3>Data Annotation for a Health Survey</h3>
        <span>Closes Dec 01, 2026 · 9 days left</span><span>Org</span>
        <span>Location Delhi · <span>Issued {issued}</span></span>
        <a class="rfp-view" href="/rfp-tender/rfp-tender-description/data-annotation/12">View</a>
      </div>"""
    (p,) = parse_samsstc(page)

    assert p.title == "Data Annotation for a Health Survey"
    assert p.url == "https://www.samsstc.com/rfp-tender/rfp-tender-description/data-annotation/12"
    assert p.date_only and is_fresh(p, NOW, 24)


def test_tendernews_reads_table_rows():
    posted = (NOW - timedelta(days=1)).strftime("%d-%b-%Y")
    page = f"""<tr>
        <td class="hide">632016</td> <td>{posted}</td> <td>28-Oct-2026</td>
        <td>India</td> <td class="hide">Refer Document.</td>
        <td> Tender For Image Annotation Services <br />
          <a id="refer" href='https://www.tendernews.com/tenderdetail.aspx?ref=632016&amp;s=0'>
          View Tender Detail </a></td></tr>"""
    (p,) = parse_tendernews(page)

    assert p.title == "Tender For Image Annotation Services"
    assert p.url.endswith("ref=632016&s=0") and p.budget == ""
    # A date with no time: yesterday still counts as "within 24 hours".
    assert is_fresh(p, NOW, 24)


def _project(title: str, **kw) -> Project:
    return Project(source="freelancer", id=title, title=title, url="https://example.com", **kw)


def test_on_topic_gates_loose_site_search_results():
    assert on_topic(_project("Remote Video Annotation"), KEYWORDS, [])
    assert on_topic(_project("Helper", summary="image labelling work"), KEYWORDS, [])
    assert not on_topic(_project("Site Verification in Daegu"), KEYWORDS, [])
    assert not on_topic(_project("Annotation intern"), KEYWORDS, [r"\bintern\b"])


def test_an_undated_listing_is_never_fresh():
    assert not is_fresh(_project("x"), NOW, 24)


def test_seen_stops_a_project_being_mailed_twice(tmp_path):
    a, b = _project("a"), _project("b")
    seen = Seen(tmp_path / "seen.json")
    seen.record([a])

    assert Seen(tmp_path / "seen.json").unseen([a, b]) == [b]


def test_digest_always_reports_every_site_even_with_nothing_new():
    subject, doc = digest.build([], {"freelancer": "111 listed",
                                     "workana": "failed (ValueError: HTTP 403)"}, 24)

    assert subject.startswith("No new annotation projects")
    assert "This mail confirms the check ran" in doc
    assert "failed (ValueError: HTTP 403)" in doc
    assert "Liceum" in doc and "only visible after login" in " ".join(doc.split())

    subject, doc = digest.build([_project("Label <cats>", posted=NOW)], {}, 24)
    assert subject.startswith("1 new annotation project ") and "Label &lt;cats&gt;" in doc
