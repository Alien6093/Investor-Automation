import os
import json
import re
import html
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, unquote

import requests
import feedparser
import gspread
from google.oauth2.service_account import Credentials

from investor_extractor import build_investor_table, extract_investors, INVESTOR_HEADER
from deal_extractor import extract_deal, is_single_deal
from summary_tabs import (build_deals_table, build_accelerator_table, dedupe_deals, DEALS_HEADER,
                          ACCELERATOR_HEADER, _program_names as program_names)

YC_HEADER = ["Program", "Batch", "Company", "One-liner", "Industry", "Location", "Website", "YC Profile"]

BASE_HEADER = ["Date", "Source", "Title", "Category", "Link"]
DEAL_HEADER = ["Company", "Amount", "Round", "Investors"]
ARTICLE_HEADER = BASE_HEADER + DEAL_HEADER
NOT_FOUND = "—"  # marks a row whose investors were looked for but not named
INVESTORS_TAB = "Investors"

# Scheduled runs only look back a few days (duplicates are skipped anyway).
# For a historical backfill, set START_DATE=YYYY-MM-DD, e.g. 2026-01-01.
DEFAULT_LOOKBACK_DAYS = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/rss+xml,application/xml,application/json,text/html;q=0.9,*/*;q=0.8",
}

# Each source is fetched with the method that gives the most history:
#   rss          - plain RSS/Atom feed (recent items only)
#   wordpress    - WordPress REST API, paginated back to START_DATE
#   sitemap      - daily/weekly sitemaps, article pages fetched for title/date
#   google_news  - Google News search restricted to the site (for sites that
#                  block automated requests or have no archive feed)
SOURCES = [
    {"name": "Entrackr", "type": "rss", "url": "https://entrackr.com/rss"},
    {"name": "Entrackr", "type": "sitemap", "pattern": "https://entrackr.com/sitemap_{date:%Y-%m-%d}.xml", "step": "day"},
    {"name": "Inc42", "type": "wordpress", "base": "https://inc42.com"},
    {"name": "YourStory", "type": "rss", "url": "https://yourstory.com/feed"},
    {"name": "YourStory", "type": "sitemap", "pattern": "https://yourstory.com/sitemap_{date:%Y}_week{week}.xml", "step": "week"},
    {"name": "BW Businessworld", "type": "google_news", "site": "businessworld.in"},
    {"name": "Y Combinator Blog", "type": "rss", "url": "https://www.ycombinator.com/blog/rss/"},
    {"name": "ET Tech Funding", "type": "rss", "url": "https://economictimes.indiatimes.com/tech/funding/rssfeeds/78570540.cms"},
    {"name": "ET Tech Startups", "type": "rss", "url": "https://economictimes.indiatimes.com/tech/startups/rssfeeds/78570550.cms"},
    {"name": "ET Tech", "type": "google_news", "site": "economictimes.indiatimes.com/tech"},
    {"name": "VCCircle", "type": "google_news", "site": "vccircle.com"},
    {"name": "TechCrunch Venture", "type": "wordpress", "base": "https://techcrunch.com", "params": {"categories": "577030455"}},
    {"name": "Crunchbase News", "type": "wordpress", "base": "https://news.crunchbase.com"},
    {"name": "e27", "type": "wordpress", "base": "https://e27.co"},
    {"name": "Indian Startup News", "type": "rss", "url": "https://indianstartupnews.com/rss"},
    {"name": "Indian Startup News", "type": "google_news", "site": "indianstartupnews.com"},
    {"name": "Startup Story Media", "type": "rss", "url": "https://startupstorymedia.com/feed/"},
    {"name": "Startup Story Media", "type": "wordpress", "base": "https://startupstorymedia.com"},
    {"name": "Entrepreneur India", "type": "rss", "url": "https://www.entrepreneur.com/en-in/rss"},
    {"name": "Livemint", "type": "rss", "url": "https://www.livemint.com/rss/companies"},
    {"name": "Moneycontrol", "type": "google_news", "site": "moneycontrol.com"},
    {"name": "Business Standard", "type": "google_news", "site": "business-standard.com"},
    {"name": "DealStreetAsia", "type": "google_news", "site": "dealstreetasia.com"},
    # LinkedIn posts / articles announcing rounds, fund closes and cohorts (indexed by Google News)
    {"name": "LinkedIn", "type": "google_news", "site": "linkedin.com", "strict": True,
     "terms": '("raised" OR "funding round" OR "led by" OR "first close" OR "final close" OR cohort OR accelerator)'},
    # Publisher-agnostic searches; the Source column shows the publisher
    {"name": "Accelerator news", "type": "google_news", "any_publisher": True, "strict": True,
     "terms": '(accelerator OR incubator) (cohort OR "applications open" OR "demo day" OR selects OR "startups for")'},
    {"name": "VC fund news", "type": "google_news", "any_publisher": True,
     "terms": '("first close" OR "final close" OR "launches fund" OR "maiden fund" OR "new fund" OR "fund of funds") '
              '(venture OR VC OR startups)'},
    {"name": "Funding news", "type": "google_news", "any_publisher": True,
     "terms": '(startup OR startups) (raises OR raised OR funding) "led by"'},
    # Global startup / VC / PE news
    {"name": "EU-Startups", "type": "rss", "url": "https://www.eu-startups.com/feed/"},
    {"name": "EU-Startups", "type": "wordpress", "base": "https://www.eu-startups.com"},
    {"name": "Sifted", "type": "rss", "url": "https://sifted.eu/feed"},
    {"name": "TechCrunch Startups", "type": "rss", "url": "https://techcrunch.com/category/startups/feed/"},
    {"name": "Tech in Asia", "type": "rss", "url": "https://www.techinasia.com/feed"},
    {"name": "Wamda", "type": "rss", "url": "https://www.wamda.com/feed"},
    {"name": "Startup Daily", "type": "rss", "url": "https://www.startupdaily.net/feed/"},
    {"name": "Startup Daily", "type": "wordpress", "base": "https://www.startupdaily.net"},
    {"name": "The SaaS News", "type": "rss", "url": "https://www.thesaasnews.com/feed"},
    {"name": "AlleyWatch", "type": "rss", "url": "https://www.alleywatch.com/feed/"},
    {"name": "AlleyWatch", "type": "wordpress", "base": "https://www.alleywatch.com"},
    {"name": "PE Hub", "type": "rss", "url": "https://www.pehub.com/feed/"},
    {"name": "Private Equity Wire", "type": "rss", "url": "https://www.privateequitywire.co.uk/feed"},
    {"name": "Ventureburn", "type": "rss", "url": "https://ventureburn.com/feed/"},
    {"name": "Business Today", "type": "rss", "url": "https://www.businesstoday.in/rss/startups"},
    # Sites that block automated requests: read through Google News
    {"name": "FinSMEs", "type": "google_news", "site": "finsmes.com"},
    {"name": "Tech Funding News", "type": "google_news", "site": "techfundingnews.com"},
    {"name": "VentureBeat", "type": "google_news", "site": "venturebeat.com"},
    {"name": "Financial Express", "type": "google_news", "site": "financialexpress.com"},
    {"name": "Sifted", "type": "google_news", "site": "sifted.eu"},
    {"name": "Tech in Asia", "type": "google_news", "site": "techinasia.com"},
    # VC blogs / newsletters and accelerator programme announcements on LinkedIn articles
    {"name": "LinkedIn Articles", "type": "google_news", "site": "linkedin.com/pulse", "strict": True,
     "terms": '("venture capital" OR "VC fund" OR accelerator OR incubator OR "funding round" OR "first close")'},
]

# Y Combinator batches published at yc-oss.github.io (public YC company directory data)
YC_BATCHES = ["winter-2026", "spring-2026", "summer-2026", "fall-2026"]

# Terms that on their own mark an article as funding / VC / accelerator news
STRONG_KEYWORDS = re.compile(
    r'\b(funding|fundraise|fundraising|pre-seed|seed round|seed funding|series [a-f]|bridge round|'
    r'venture capital|venture capitalist|vc firm|vc fund|venture fund|corporate vc|corporate venture|cvc|'
    r'flipkart ventures|angel investors?|angel network|angel round|family office|limited partners?|'
    r'first close|final close|launches fund|new fund|maiden fund|fund size|accelerator|incubator|'
    r'cohort|demo day|startup program|startup programme|y combinator|techstars|lead investor)\b',
    re.IGNORECASE
)

# Broader terms that only count when the article is not stock-market / public-finance news
WEAK_KEYWORDS = re.compile(
    r'\b(funded|raises|raised|raising|raise|backed by|investors?|valuation|unicorn|corpus)\b',
    re.IGNORECASE
)
EXCLUDE_KEYWORDS = re.compile(
    r'\b(shares?|stocks?|sensex|nifty|dalal street|etfs?|mutual funds?|disinvestment|ipo|listing|'
    r'dividend|bonds?|q[1-4] results|quarterly results|govt|government|qip|ncds?|rights issue|'
    r'target price|price target|brokerage|sgb|sovereign gold|gold|silver|sip|nav|redemption|tax)\b',
    re.IGNORECASE
)


def is_relevant(text):
    if STRONG_KEYWORDS.search(text):
        return True
    return bool(WEAK_KEYWORDS.search(text)) and not EXCLUDE_KEYWORDS.search(text)

GOOGLE_NEWS_TERMS = (
    '(funding OR raises OR investors OR "venture capital" OR accelerator OR incubator '
    'OR "seed round" OR "series a" OR "series b" OR fund OR cohort)'
)


def categorize_article(text):
    text_lower = text.lower()
    if any(term in text_lower for term in ["accelerator", "cohort", "demo day", "incubator", "startup program"]):
        return "Accelerator Program"
    elif re.search(r"pre-seed|seed|series [a-f]|raise|funding|round", text_lower):
        return "Startup Funding"
    elif any(term in text_lower for term in ["venture capital", "vc", "fund", "flipkart ventures", "family office", "angel"]):
        return "VC / Fund News"
    return "General Investment"


def clean_text(text):
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def get(session, url, **kwargs):
    for attempt in range(5):
        try:
            resp = session.get(url, timeout=60, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            return resp
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return None


def to_utc_naive(dt):
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ---------------------------------------------------------------- fetchers

def fetch_rss(session, source, start):
    resp = get(session, source["url"])
    if resp is None or resp.status_code != 200:
        print(f"[{source['name']}] WARNING: RSS returned {getattr(resp, 'status_code', 'no response')}")
        return []
    feed = feedparser.parse(resp.content)
    articles = []
    for entry in feed.entries:
        pub_tuple = entry.get("published_parsed") or entry.get("updated_parsed")
        if not pub_tuple:
            continue
        pub_date = datetime(*pub_tuple[:6])
        if pub_date < start:
            continue
        articles.append({
            "date": pub_date,
            "title": clean_text(entry.get("title", "")),
            "summary": clean_text(entry.get("summary", "")),
            "link": entry.get("link", ""),
        })
    return articles


def fetch_wordpress(session, source, start):
    # Query in 2-week windows: some sites reject deep page numbers, so this
    # keeps every query to a few pages.
    articles = []
    window_start = start
    now = datetime.utcnow()
    while window_start <= now:
        window_end = window_start + timedelta(days=14)
        page = 1
        while True:
            params = {
                "after": window_start.strftime("%Y-%m-%dT%H:%M:%S"),
                "before": window_end.strftime("%Y-%m-%dT%H:%M:%S"),
                "per_page": 100,
                "page": page,
                "orderby": "date",
                "order": "desc",
                "_fields": "date_gmt,link,title,excerpt",
                **source.get("params", {}),
            }
            resp = get(session, f"{source['base']}/wp-json/wp/v2/posts", params=params)
            if resp is None or resp.status_code != 200:
                print(f"[{source['name']}] WARNING: WordPress API returned "
                      f"{getattr(resp, 'status_code', 'no response')} for {window_start:%Y-%m-%d} page {page}")
                if not articles and resp is not None and resp.status_code in (401, 403, 404):
                    return articles  # API disabled on this site; the RSS source still covers new posts
                break
            posts = resp.json()
            for post in posts:
                articles.append({
                    "date": datetime.fromisoformat(post["date_gmt"]),
                    "title": clean_text(post["title"]["rendered"]),
                    "summary": clean_text(post.get("excerpt", {}).get("rendered", "")),
                    "link": post["link"],
                })
            total_pages = int(resp.headers.get("X-WP-TotalPages", page))
            if not posts or page >= total_pages:
                break
            page += 1
        window_start = window_end
    return articles


def slug_text(url):
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"-\d{5,}$", "", slug)  # Entrackr appends a numeric article id
    return slug.replace("-", " ")


def fetch_page_meta(session, url):
    """Return (title, published datetime or None) from an article page."""
    resp = get(session, url)
    if resp is None or resp.status_code != 200:
        return None, None
    page = resp.text
    title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', page) \
        or re.search(r"<title[^>]*>(.*?)</title>", page, re.S)
    published = re.search(r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"', page) \
        or re.search(r'"datePublished"\s*:\s*"([^"]+)"', page)
    pub_date = None
    if published:
        try:
            pub_date = to_utc_naive(datetime.fromisoformat(published.group(1).replace("Z", "+00:00")))
        except ValueError:
            pass
    return (clean_text(title.group(1)) if title else None), pub_date


def fetch_sitemap(session, source, start):
    today = datetime.utcnow()
    sitemap_urls = []
    if source["step"] == "day":
        day = start
        while day <= today:
            sitemap_urls.append(source["pattern"].format(date=day))
            day += timedelta(days=1)
    else:
        seen = set()
        day = start
        while day <= today + timedelta(days=7):
            year, week = day.year, day.isocalendar()[1]
            if (year, week) not in seen:
                seen.add((year, week))
                sitemap_urls.append(source["pattern"].format(date=day, week=week))
            day += timedelta(days=7)

    candidates = {}
    for sm_url in sitemap_urls:
        resp = get(session, sm_url)
        if resp is None or resp.status_code != 200:
            continue
        for block in re.findall(r"<url>(.*?)</url>", resp.text, re.S):
            loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block)
            lastmod = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", block)
            if not loc:
                continue
            link = loc.group(1)
            # Pre-filter on the URL slug so only likely-relevant pages are fetched.
            slug = slug_text(link)
            if not (STRONG_KEYWORDS.search(slug) or WEAK_KEYWORDS.search(slug)):
                continue
            date = None
            if lastmod:
                try:
                    date = to_utc_naive(datetime.fromisoformat(lastmod.group(1).replace("Z", "+00:00")))
                except ValueError:
                    pass
            candidates[link] = date
    print(f"[{source['name']}] {len(sitemap_urls)} sitemaps, {len(candidates)} keyword-matching URLs")

    with ThreadPoolExecutor(max_workers=8) as pool:
        metas = list(pool.map(lambda link: fetch_page_meta(session, link), candidates))

    articles = []
    for (link, sitemap_date), (title, pub_date) in zip(candidates.items(), metas):
        date = pub_date or sitemap_date
        if date is None or date < start:
            continue
        articles.append({
            "date": date,
            "title": title or slug_text(link).capitalize(),
            "summary": "",
            "link": link,
        })
    return articles


def fetch_google_news(session, source, start):
    articles = []
    window = timedelta(days=7)  # Google News returns at most ~100 results per query
    day = start
    today = datetime.utcnow()
    while day <= today:
        end = day + window
        terms = source.get("terms", GOOGLE_NEWS_TERMS)
        site = "" if source.get("any_publisher") else f"site:{source['site']} "
        query = f"{site}{terms} after:{day:%Y-%m-%d} before:{end:%Y-%m-%d}"
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        resp = get(session, url)
        if resp is not None and resp.status_code == 200:
            for entry in feedparser.parse(resp.content).entries:
                if not entry.get("published"):
                    continue
                pub_date = to_utc_naive(parsedate_to_datetime(entry.published))
                if pub_date < start:
                    continue
                title = clean_text(entry.get("title", ""))
                publisher = entry.get("source", {}).get("title", "")
                if publisher and title.endswith(f" - {publisher}"):
                    title = title[: -len(publisher) - 3]
                articles.append({
                    "date": pub_date, "title": title[:300], "summary": "", "link": entry.get("link", ""),
                    "publisher": publisher if source.get("any_publisher") else "",
                })
        day = end
        time.sleep(1)
    return articles


FETCHERS = {
    "rss": fetch_rss,
    "wordpress": fetch_wordpress,
    "sitemap": fetch_sitemap,
    "google_news": fetch_google_news,
}


# ---------------------------------------------------------------- sheet

def setup_google_sheet():
    creds_json = json.loads(os.environ["GCP_SERVICE_ACCOUNT_KEY"])
    # Opening a sheet by its title searches Google Drive, so the Drive
    # scope is required alongside the Sheets scope.
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    client = gspread.authorize(creds)
    sheet_id = os.environ.get("SHEET_ID")
    if sheet_id:
        return client.open_by_key(sheet_id).sheet1
    return client.open("VC & Funding Tracker").sheet1


def get_start_date():
    raw = (os.environ.get("START_DATE") or "").strip()
    if raw:
        return datetime.strptime(raw, "%Y-%m-%d")
    return datetime.utcnow() - timedelta(days=DEFAULT_LOOKBACK_DAYS)


TEXT_STATS = Counter()
WORDPRESS_BASES = {s["base"]: s.get("params", {}) for s in SOURCES if s["type"] == "wordpress"}


def _norm_link(url):
    return unquote(url).rstrip("/").lower()


def fetch_wordpress_texts(session, base, rows):
    """Excerpt + opening paragraphs for many WordPress posts, 100 per request."""
    wanted = {_norm_link(row[4]) for row in rows}
    dates = [datetime.strptime(row[0][:10], "%Y-%m-%d") for row in rows]
    texts = {}
    window_start, last = min(dates) - timedelta(days=1), max(dates) + timedelta(days=1)
    while window_start <= last:
        window_end = window_start + timedelta(days=7)
        page = 1
        while True:
            params = {
                "after": window_start.strftime("%Y-%m-%dT%H:%M:%S"),
                "before": window_end.strftime("%Y-%m-%dT%H:%M:%S"),
                "per_page": 100, "page": page, "_fields": "link,excerpt,content",
                **WORDPRESS_BASES.get(base, {}),
            }
            resp = get(session, f"{base}/wp-json/wp/v2/posts", params=params)
            TEXT_STATS[f"{base} {getattr(resp, 'status_code', 'no response')}"] += 1
            if resp is None or resp.status_code != 200:
                break
            posts = resp.json()
            for post in posts:
                link = _norm_link(post.get("link", ""))
                if link not in wanted:
                    continue
                paragraphs = re.findall(r"(?is)<p[^>]*>(.*?)</p>", post.get("content", {}).get("rendered", ""))[:10]
                texts[link] = " ".join([clean_text(post.get("excerpt", {}).get("rendered", ""))]
                                       + [clean_text(p) for p in paragraphs])[:4000]
            if not posts or page >= int(resp.headers.get("X-WP-TotalPages", page)):
                break
            page += 1
        window_start = window_end
    return texts


def fetch_article_text(session, url):
    """Summary + opening paragraphs of an article, where investors are usually named."""
    if "news.google.com" in url:
        return ""  # Google News redirect links can't be resolved without a browser
    resp = get(session, url)
    TEXT_STATS[getattr(resp, "status_code", "no response")] += 1
    if resp is None or resp.status_code != 200:
        return ""
    page = resp.text
    parts = re.findall(r'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="([^"]*)"', page)
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    # Skip short navigation / caption paragraphs
    parts += [p for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body) if len(clean_text(p)) > 60][:10]
    return " ".join(clean_text(part) for part in parts if part.strip())[:4000]


def add_deal_columns(session, rows):
    """Fill Company / Amount / Round / Investors (columns F-I) for rows that lack them."""
    todo = [row for row in rows if len(row) < 9 or not row[8]]
    if not todo:
        return 0

    def needs_article(row):
        title, link = row[2], row[4]
        return not extract_investors(title) and is_single_deal(title) and "news.google.com" not in link

    to_fetch = [row for row in todo if needs_article(row)]
    texts = {}
    # WordPress sites: bulk API reads (per-article requests get rate-limited)
    for base in WORDPRESS_BASES:
        wp_rows = [row for row in to_fetch if row[4].startswith(base)]
        if wp_rows:
            by_link = fetch_wordpress_texts(session, base, wp_rows)
            texts.update({row[4]: by_link.get(_norm_link(row[4]), "") for row in wp_rows})
    # Other sites: read the article page
    page_links = [row[4] for row in to_fetch if row[4] not in texts]
    with ThreadPoolExecutor(max_workers=8) as pool:
        texts.update(zip(page_links, pool.map(lambda link: fetch_article_text(session, link), page_links)))
    got_text = sum(1 for text in texts.values() if text)
    print(f"Deal columns: {len(todo)} rows to fill, {len(to_fetch)} articles read for investor names "
          f"({got_text} with text; HTTP status counts {dict(TEXT_STATS)})")

    for row in todo:
        deal = extract_deal(row[2], texts.get(row[4], ""))
        row[5:] = []
        row += [
            deal["company"],
            deal["amount"],
            deal["round"],
            "; ".join(deal["investors"]) or NOT_FOUND,
        ]
    return len(todo)


def title_key(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())[:90]


def fetch_yc_companies(session):
    """Startups in Y Combinator's 2026 batches (from the public yc-oss directory data)."""
    rows = []
    for batch in YC_BATCHES:
        resp = get(session, f"https://yc-oss.github.io/api/batches/{batch}.json")
        if resp is None or resp.status_code != 200:
            continue
        for company in resp.json():
            rows.append([
                "Y Combinator",
                company.get("batch") or batch.replace("-", " ").title(),
                company.get("name", ""),
                company.get("one_liner", ""),
                company.get("industry", "") or ", ".join(company.get("industries", [])[:3]),
                company.get("all_locations", ""),
                company.get("website", ""),
                f"https://www.ycombinator.com/companies/{company.get('slug', '')}",
            ])
    print(f"Y Combinator: {len(rows)} companies in {', '.join(YC_BATCHES)}")
    return rows


def write_tab(spreadsheet, name, header, table):
    try:
        tab = spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        tab = spreadsheet.add_worksheet(title=name, rows=len(table) + 10, cols=len(header))
    tab.clear()
    tab.update([header] + table, "A1")
    tab.freeze(rows=1)
    print(f"{name} tab updated: {len(table)} rows.")


def run():
    start = get_start_date()
    print(f"Collecting articles published since {start:%Y-%m-%d %H:%M} UTC")

    sheet = setup_google_sheet()
    print(f"Connected to sheet: {sheet.spreadsheet.title} / {sheet.title}")
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"

    session = requests.Session()
    session.headers.update(HEADERS)

    all_values = sheet.get_all_values()
    has_header = bool(all_values) and all_values[0][:5] == BASE_HEADER
    if not dry_run:
        if not has_header:
            sheet.insert_row(ARTICLE_HEADER, 1)
            sheet.freeze(rows=1)
            print("Added header row to the articles tab.")
        elif all_values[0][:9] != ARTICLE_HEADER:
            sheet.update([ARTICLE_HEADER], "A1")
            print("Extended header row with Company / Amount / Round / Investors.")
    existing_rows = [row for row in (all_values[1:] if has_header else all_values) if any(row[:5])]

    # Fill deal columns for existing rows that don't have them yet (first run: the whole backfill).
    # REFRESH_DEALS=true re-extracts them for every row, e.g. after the extraction rules improve.
    if os.environ.get("REFRESH_DEALS", "").lower() == "true":
        for row in existing_rows:
            del row[5:]
        print("Re-extracting Company / Amount / Round / Investors for all existing rows.")
    filled = add_deal_columns(session, existing_rows)
    if filled and not dry_run:
        sheet.update([row[5:9] for row in existing_rows], f"F2:I{len(existing_rows) + 1}")
        print(f"Filled deal columns for {filled} existing rows.")

    # Existing links (column E) and headlines, used to avoid duplicate rows. The same story
    # can arrive twice (e.g. directly from Entrackr and again through Google News).
    existing_urls = {row[4] for row in existing_rows}
    existing_titles = {title_key(row[2]) for row in existing_rows}
    new_rows = []

    only = {name.strip().lower() for name in os.environ.get("ONLY_SOURCES", "").split(",") if name.strip()}
    for source in SOURCES:
        if only and source["name"].lower() not in only:
            continue
        try:
            articles = FETCHERS[source["type"]](session, source, start)
        except Exception as e:
            print(f"[{source['name']}] ERROR ({source['type']}): {e}")
            continue

        added = 0
        for article in articles:
            text = f"{article['title']} {article['summary']}"
            if not is_relevant(text):
                continue
            # Noisy sources (LinkedIn posts, worldwide accelerator news): keep only rows that
            # name a company, an investor or an accelerator program
            if source.get("strict"):
                deal = extract_deal(article["title"])
                if not (deal["company"] or deal["investors"] or program_names(article["title"])):
                    continue
            link = article["link"]
            if not link or link in existing_urls or title_key(article["title"]) in existing_titles:
                continue
            existing_urls.add(link)
            existing_titles.add(title_key(article["title"]))
            new_rows.append([
                article["date"].strftime("%Y-%m-%d %H:%M"),
                article.get("publisher") or source["name"],
                article["title"],
                categorize_article(text),
                link,
            ])
            added += 1
        print(f"[{source['name']}] ({source['type']}) fetched {len(articles)}, {added} new relevant")

    new_rows.sort(key=lambda row: row[0])
    add_deal_columns(session, new_rows)
    if new_rows and dry_run:
        print(f"DRY RUN: would add {len(new_rows)} rows.")
    elif new_rows:
        sheet.append_rows(new_rows)
        print(f"Successfully added {len(new_rows)} relevant funding/VC items.")
    else:
        print("No new funding or accelerator updates found.")

    all_rows = existing_rows + new_rows
    with_investors = sum(1 for row in all_rows if row[8] != NOT_FOUND)
    deals = [row for row in all_rows if row[5]]
    deals_with_investors = sum(1 for row in deals if row[8] != NOT_FOUND)
    print(f"Rows with investor names: {with_investors} of {len(all_rows)}; "
          f"single-deal rows (Company filled): {len(deals)}, of which {deals_with_investors} name investors")
    if dry_run:
        print("DRY RUN sample (Title | Company | Amount | Round | Investors):")
        for row in all_rows[:: max(1, len(all_rows) // 60)]:
            print("   ", " | ".join([row[2][:70]] + row[5:9]))

    tabs = [
        ("Deals", DEALS_HEADER, build_deals_table(all_rows)),
        (INVESTORS_TAB, INVESTOR_HEADER, build_investor_table(dedupe_deals(all_rows))),
        ("Accelerators", ACCELERATOR_HEADER, build_accelerator_table(all_rows)),
        ("Accelerator Startups", YC_HEADER, fetch_yc_companies(session)),
    ]
    for name, header, table in tabs:
        if dry_run:
            print(f"DRY RUN: {name} tab would have {len(table)} rows. First 15:")
            for row in table[:15]:
                print("   ", " | ".join(str(v)[:60] for v in row[:6]))
        else:
            write_tab(sheet.spreadsheet, name, header, table)


if __name__ == "__main__":
    run()
