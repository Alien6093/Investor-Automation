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
- **Investors** tab: rebuilt every run from the Investors column: investor /
  fund / accelerator name, type, number of deals, first and latest mention,
  and the latest headline and link.

Sources: Entrackr, Inc42, YourStory, BW Businessworld, VCCircle, ET Tech,
TechCrunch Venture, Crunchbase News, e27, Y Combinator blog. Sites that block
automated requests (BW Businessworld) or have no archive feed are read through
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
