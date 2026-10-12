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
  event sites that block or sometimes refuse GitHub's servers (Eventbrite, 10times, AllEvents).
- The same event seen in several places is one row: rows are matched by an
  event-specific link (registration / event page; not an organiser page, linktr.ee
  or short link) with the same date, or by event name + date. luma.com / lu.ma and
  eventbrite.co.in / .com count as the same site.
- Only events dated today or later, held in India (an event abroad is skipped even
  when Indian founders are mentioned).
- Event news goes to the Events tab only: the funding-news run skips articles that
  are already in Events (the Google News link is stored next to the publisher's).
- **When it runs:** the Chrome extension starts this workflow at each of its 3 daily
  runs (random times between 9 AM and 7 PM IST), so both collect at the same times.
  GitHub's own schedule starts this repo's jobs hours late, so it is only a fallback:
  once a day it collects if the extension started no run that day. Every run is logged
  in the **Events Run Log** tab. **Actions → Events Fetcher → Run workflow** collects
  right away.
- Row 1 of the Events tab must stay the header: rows are written by position, so the
  job stops instead of writing when the header was moved.

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
