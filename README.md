# Investor-Automation

Daily GitHub Actions job that collects funding, VC / fund and accelerator news
into the **VC & Funding Tracker** Google Sheet.

## What it does

- **Sheet1**: one row per article, de-duplicated by link:
  `Date | Source | Title | Category | Link | Company | Amount | Round | Investors`.
  Company / Amount / Round / Investors are filled for single-deal headlines.
  Investors come from the headline, or from the article's summary and opening
  paragraphs when the headline doesn't name them; several are separated by `; `.
  `—` means no investor was named (or the row isn't about one deal).
- **Deals** tab: one row per funding round (Company, Amount, Round, Investors,
  headline, link), newest first. Repeat coverage of the same round is counted once.
- **Investors** tab: every investor / fund / accelerator named in a deal, with
  type, number of deals, first and latest mention, and the latest headline.
- **Accelerators** tab: accelerator / incubator programs seen in the news, with
  the companies mentioned alongside them.
- **Accelerator Startups** tab: companies in Y Combinator's 2026 batches (from
  the public yc-oss.github.io directory data).

All tabs except Sheet1 are rebuilt on every run, so edit Sheet1, not them.

## Events tab (fetch_events.py)

Upcoming India-only funding events, investor meets, demo days, pitch events and
startup-investor networking, one row per event:
`Event name | Event date | City / Online | Organizer | Registration link | Sources | Links | Author profile URLs | First added | Last seen`.

- Sources: Luma, Meetup, AllEvents, Konfhub, Commudle, Headstart, event coverage
  in Google News (India edition) and the India news sites above. The Chrome
  extension (master-extension repo) adds events from LinkedIn, X, Reddit and the
  event sites that block GitHub's servers (Eventbrite, District, 10times, TiE, Townscript).
- The same event seen in several places is one row: rows are matched by
  registration / event link, or by event name + date, and the new source, link
  and author are added to that row.
- Only events dated today or later, found in posts / articles from the last 7 days.
- Event news goes to the Events tab only: once an article is in Events, the
  funding-news run doesn't add it to Sheet1.
- Runs 3 times a day at random times between 9 AM and 7 PM IST, 2 to 3 hours
  apart (`.github/workflows/events_fetch.yml`). Each run is logged in the
  **Events Run Log** tab, which the schedule uses to catch up missed runs.
  **Actions → Events Fetcher → Run workflow** collects right away.

Sources: Entrackr, Inc42, YourStory, BW Businessworld, VCCircle, ET Tech,
TechCrunch Venture, Crunchbase News, e27, Y Combinator blog, Indian Startup
News, Startup Story Media, Livemint, Moneycontrol, Business Standard,
DealStreetAsia, LinkedIn posts, plus Google News searches (any publisher) for
accelerator cohorts, VC fund launches / closes and "led by" funding news.
Sites that block automated requests or have no archive feed are read through
Google News, so those rows link via `news.google.com`.

## Running it

The workflow `.github/workflows/daily_vc_fetch.yml` runs daily at 10:00 AM IST
and looks back 3 days. To run it by hand: **Actions → Daily VC & Accelerator
Fetcher → Run workflow**, with optional inputs:

- `start_date` (`YYYY-MM-DD`): backfill everything since that date.
- `dry_run`: print what would be added without writing to the sheet.

## Setup

Repository secrets (Settings → Secrets and variables → Actions):

- `GCP_SERVICE_ACCOUNT_KEY`: the service account JSON key. The Google Sheets
  API and Google Drive API must be enabled in its project, and the sheet shared
  with the service account's email as Editor.
- `SHEET_ID` (optional): the ID from the sheet URL. Without it the sheet is
  found by its name.

Tests: `python -m unittest discover -s tests -t .`
