# Investor-Automation

Daily GitHub Actions job that collects funding, VC / fund and accelerator news
into the **VC & Funding Tracker** Google Sheet.

## What it does

- **Sheet1**: one row per article, de-duplicated by link:
  `Date | Source | Title | Category | Link | Company | Amount | Round | Investors | Sector`.
  Company / Amount / Round / Investors are filled for single-deal headlines.
  Investors come from the headline, or from the article's summary and opening
  paragraphs when the headline doesn't name them; several are separated by `; `.
  `—` means no investor was named (or the row isn't about one deal).
  Sector tags come from the headline (several are separated by `; `). The social
  sectors are Influencer Marketing, Creator Economy, Social Media Management,
  Social Media and Social Commerce; broad ones (AI, Fintech, D2C, ...) cover the rest.
- **Social & Creator** tab: every funding round, investment, VC post and program
  about social media / creator economy / influencer marketing startups, newest first.
- **Deals** tab: one row per funding round (Company, Amount, Round, Investors,
  headline, link), newest first. Repeat coverage of the same round is counted once.
- **Investors** tab: every investor / fund / accelerator named in a deal, with
  type, number of deals, first and latest mention, the latest headline, how many
  social / creator deals they did, and the sectors of their deals.
- **Accelerators** tab: accelerator / incubator programs seen in the news, with
  the companies mentioned alongside them.
- **Accelerator Startups** tab: companies in Y Combinator's 2026 batches (from
  the public yc-oss.github.io directory data).

All tabs except Sheet1 are rebuilt on every run, so edit Sheet1, not them.

Sources: Entrackr, Inc42, YourStory, BW Businessworld, VCCircle, ET Tech,
TechCrunch Venture, Crunchbase News, e27, Y Combinator blog, Indian Startup
News, Startup Story Media, Livemint, Moneycontrol, Business Standard,
DealStreetAsia, LinkedIn posts and articles, EU-Startups, Sifted, TechCrunch
Startups, Tech in Asia, Wamda, Startup Daily, The SaaS News, AlleyWatch, PE Hub,
Private Equity Wire, Ventureburn, Business Today, FinSMEs, Tech Funding News,
VentureBeat, Financial Express, Net Influencer, Influencer Marketing Hub, Social
Media Today, Digiday, Adweek, afaqs, MediaNews4U, Exchange4media, Storyboard18,
Tubefilter, plus Google News searches (any publisher) for accelerator cohorts,
VC fund launches / closes, "led by" funding news, and social media / creator /
influencer marketing deals and VC commentary.
Sites that block automated requests or have no archive feed are read through
Google News, so those rows link via `news.google.com`.

## Running it

The workflow `.github/workflows/daily_vc_fetch.yml` runs daily at 10:00 AM IST
and looks back 3 days. To run it by hand: **Actions → Daily VC & Accelerator
Fetcher → Run workflow**, with optional inputs:

- `start_date` (`YYYY-MM-DD`): backfill everything since that date.
- `only_sources`: comma-separated source names to fetch (e.g. `EU-Startups,Sifted`),
  handy for backfilling a newly added source.
- `refresh_deals`: re-extract Company / Amount / Round / Investors for every row.
- `dry_run`: print what would be added without writing to the sheet.

## Setup

Repository secrets (Settings → Secrets and variables → Actions):

- `GCP_SERVICE_ACCOUNT_KEY`: the service account JSON key. The Google Sheets
  API and Google Drive API must be enabled in its project, and the sheet shared
  with the service account's email as Editor.
- `SHEET_ID` (optional): the ID from the sheet URL. Without it the sheet is
  found by its name.
