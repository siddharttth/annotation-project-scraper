# annotation-project-scraper

A daily email of freshly posted data annotation and AI-training projects,
collected from public freelance and tender listings.

Once a day it reads each site, keeps the listings that are actually about
annotation, keeps the ones posted in the last 24 hours, drops anything it has
already sent, and mails the rest with a link to each.

```
~200 listings  ->  ~16 on topic  ->  2 posted in the last 24h  ->  your inbox
```

## Sites

| Site | How it is read | Posted date |
|---|---|---|
| [Freelancer](https://www.freelancer.com/) | public projects API | exact time |
| [Truelancer](https://www.truelancer.com/freelance-ai-data-annotation-jobs) | data embedded in the listing page | exact time |
| [Workana](https://www.workana.com/jobs?language=en) | data embedded in the search page | relative ("3 hours ago") |
| [SAMS-STC](https://www.samsstc.com/rfp-tender) | RFP list page | day only |
| [TenderNews](https://www.tendernews.com/tenders/latest-tender/ai-data-annotation.html) | tender table | day only |
| [Liceum](https://liceum.ai/) | **not read** — projects are only visible after login | — |
| [OpenTrain](https://www.opentrain.ai/) | **not read** — projects are only visible after login | — |

Only public pages and public APIs are requested, once a day each. Nothing
behind a login is touched. The two login-only sites are listed at the bottom of
every mail with a link, so they are not forgotten.

A mail is sent every day, including days with nothing new, and every mail ends
with a per-site status line. A site that fails or changes its layout shows up
there as `failed (...)` instead of quietly returning nothing.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m scraper run              # build out/digest.html, no email
python -m scraper run --hours 72   # wider window, useful for a first look
python -m scraper run --send       # ...and email it
```

For `--send`, copy `.env.example` to `.env` and fill it in. Gmail needs an
[App Password](https://myaccount.google.com/apppasswords), not your login
password. `MAIL_TO` takes several addresses separated by commas.

## Tune it

Everything is in [`config.yaml`](config.yaml):

- `fresh_hours` — the freshness window (24). Sites that give a day without a
  time count today and yesterday.
- `search_terms` — what is typed into the sites that have a search box.
- `keywords` / `exclude` — regexes matched against title and summary. The
  sites' own searches are loose (a search for "data annotation" returns bridge
  tenders and photo shoots), so this is what keeps the mail on topic.
- `sources` — read a subset of the sites.

## Schedule

[`.github/workflows/daily.yml`](.github/workflows/daily.yml) runs it every day
and mails the digest. Repository secrets it needs (Settings → Secrets and
variables → Actions): `SMTP_USER`, `SMTP_PASS`, `MAIL_TO`.

The record of what was already mailed (`seen.json`) is carried between runs
with `actions/cache`, not committed.

GitHub's scheduler is best-effort and can start a job hours late; the comment
on the `cron` line explains the offset used here. Use **Actions → daily
annotation digest → Run workflow** to trigger it by hand.

## Layout

```
scraper/
  sources.py   Project dataclass, one pure parser per site, fetch_all
  select.py    keyword gate, freshness window, seen.json
  digest.py    HTML email (inline CSS only — Gmail strips <style>)
  mailer.py    SMTP
  cli.py       argparse: run
config.yaml    window, search terms, keywords
tests/         parsers and selection, no network
```

Each `parse_*` takes an already-fetched body and returns `list[Project]`, so a
site changing its markup is a one-function fix with a fixture test beside it.

```bash
python -m pytest tests -q
```
