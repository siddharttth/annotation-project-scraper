# Setup guide

How to get your own copy of this project emailing you every day.

**Time:** about 15 minutes. **Cost:** free. **You need:** a GitHub account and
a Gmail account.

There are two parts. Part A gets the daily email running on GitHub and needs
only a browser. Part B runs it on your own computer, which you only need if
you want to change the code or the keywords and try them before pushing.

| What | Link |
|---|---|
| This project | https://github.com/siddharttth/annotation-project-scraper |
| Create a GitHub account | https://github.com/signup |
| Copy a repo into your account | https://github.com/new/import |
| Turn on Google 2-Step Verification | https://myaccount.google.com/signinoptions/two-step-verification |
| Create a Gmail App Password | https://myaccount.google.com/apppasswords |
| Download Python | https://www.python.org/downloads/ |
| Download Git | https://git-scm.com/downloads |
| Cron schedule helper | https://crontab.guru/ |

---

## Part A — the daily email, on GitHub

### 1. Copy the repo into your account

1. Sign in to GitHub and open https://github.com/new/import
2. **The URL for your source repository:**
   `https://github.com/siddharttth/annotation-project-scraper`
3. Leave the username and token fields empty (the source is public).
4. **Repository name:** `annotation-project-scraper`
5. Choose **Public** or **Private**, then click **Begin import**.

Use Import and not the Fork button: scheduled runs are switched off in forks
and are unreliable there even after you switch them on.

### 2. Create a Gmail App Password

The project sends mail through your Gmail account. Gmail will not accept your
normal password for this; it needs a 16-character App Password.

1. Turn on 2-Step Verification if it is off:
   https://myaccount.google.com/signinoptions/two-step-verification
2. Open https://myaccount.google.com/apppasswords
3. Type a name such as `annotation scraper` and click **Create**.
4. Copy the 16 characters. Remove the spaces when you paste it later.

### 3. Add three secrets to your repo

In your new repo: **Settings → Secrets and variables → Actions → New
repository secret**. The direct link is
`https://github.com/<your-username>/annotation-project-scraper/settings/secrets/actions`

Add these three, one at a time:

| Name | Value |
|---|---|
| `SMTP_USER` | your Gmail address |
| `SMTP_PASS` | the App Password from step 2, without spaces |
| `MAIL_TO` | where the digest should go |

`MAIL_TO` can hold several addresses separated by commas:
`you@gmail.com, teammate@gmail.com`

### 4. Run it once by hand

1. Open the **Actions** tab of your repo. If GitHub shows a button asking you
   to enable workflows, click it.
2. Click **daily annotation digest** in the left column.
3. Click **Run workflow**, leave `dry_run` unticked, and click the green
   **Run workflow** button.
4. Wait about a minute and refresh. A green tick means it worked.

Check your inbox. The first mail lists annotation projects posted in the last
24 hours, or says that there were none. Either one means the setup is done.

### 5. The daily schedule

From now on GitHub runs it every day without you. Two things to know:

- **GitHub starts scheduled jobs late**, sometimes by several hours. The
  schedule in this repo is set about six hours early to compensate, aiming at
  11:30 AM India time. Your mail may arrive earlier or later than that.
- **GitHub pauses schedules on a public repo with no activity for 60 days.**
  It emails you first; re-enable the workflow from the Actions tab.

To change the time, edit the `cron` line in
[`.github/workflows/daily.yml`](.github/workflows/daily.yml). It is written in
UTC. India is UTC+5:30, so subtract 5 hours 30 minutes:

| You want (IST) | Write (UTC) |
|---|---|
| 8:00 AM | `30 2 * * *` |
| 11:30 AM | `0 6 * * *` |
| 6:00 PM | `30 12 * * *` |

https://crontab.guru/ shows what any cron line means.

---

## Part B — run it on your computer (optional)

### 1. Install Python and Git

- **Python 3.10 or newer:** https://www.python.org/downloads/
  On Windows, tick **Add python.exe to PATH** on the first installer screen.
- **Git:** https://git-scm.com/downloads

Check both in a new terminal:

```bash
python3 --version     # on Windows: python --version
git --version
```

### 2. Get the code

Use your own copy from Part A, so you can push changes to it:

```bash
git clone https://github.com/<your-username>/annotation-project-scraper.git
cd annotation-project-scraper
```

### 3. Install

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell says running scripts is disabled, run this once in the same
window and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 4. Try it, without email

```bash
python -m scraper run
```

You should see one line per site, then the counts:

```
[1/3] reading sites
  freelancer  123 listed
  truelancer  15 listed
  workana     4 listed
  samsstc     21 listed
  tendernews  50 listed
[2/3] filtering
  213 listed -> 21 on topic -> 2 in the last 24h -> 2 not sent before
[3/3] digest
  wrote out/digest.html
```

Open `out/digest.html` in a browser to see the mail. To look further back than
a day, add `--hours 72`.

### 5. Send the email from your computer

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Open `.env` and fill in the same three values as the GitHub secrets
(`SMTP_USER`, `SMTP_PASS`, `MAIL_TO`). Then:

```bash
python -m scraper run --send
```

`.env` is in `.gitignore`. Never commit it or paste it anywhere.

### 6. Check your changes

```bash
python -m pytest tests -q
```

---

## Changing what you get

Everything is in [`config.yaml`](config.yaml). Edit it on GitHub (the pencil
icon) or locally and push.

| Setting | What it does |
|---|---|
| `fresh_hours` | how far back to look (24) |
| `search_terms` | what is searched on Freelancer and Workana |
| `keywords` | a listing is kept only if its title or summary matches one |
| `exclude` | a listing matching one of these is dropped |
| `sources` | read only some of the sites |

Too few results: add words to `keywords` and `search_terms`, or raise
`fresh_hours`. Off-topic results: add a pattern to `exclude`.

## Sites covered

Freelancer, Truelancer, Workana, SAMS-STC and TenderNews are read. Liceum and
OpenTrain only show projects after you log in, so they are not read; every
mail links to them so you can check them by hand.

## Troubleshooting

| What you see | Cause | Fix |
|---|---|---|
| Run is red, log says `KeyError: 'SMTP_USER'` | a secret is missing | add all three secrets, with these exact names |
| `Username and Password not accepted` | normal Gmail password used | use the 16-character App Password, no spaces |
| No App Password page | 2-Step Verification is off | turn it on first, then retry the link |
| Run is green but no mail | landed in spam, or wrong `MAIL_TO` | check spam; re-enter the `MAIL_TO` secret |
| A site shows `failed (...)` at the bottom of the mail | the site was down, blocked the request, or changed its page | usually clears the next day; if it stays, its parser in `scraper/sources.py` needs updating |
| No run appears at the scheduled time | GitHub's scheduler is late | wait a few hours, or use **Run workflow** |
| `python: command not found` | Python not on PATH | reinstall with the PATH box ticked; on macOS/Linux use `python3` |
| `No module named scraper` | wrong folder, or venv not active | `cd` into the project folder and activate `.venv` |
| Same project never appears twice | by design | the run remembers what it already sent |
