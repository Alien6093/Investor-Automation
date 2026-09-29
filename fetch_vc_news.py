import os
import json
import re
import html
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests
import feedparser
import gspread
from google.oauth2.service_account import Credentials

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
    {"name": "Medianama", "type": "wordpress", "base": "https://www.medianama.com"},
]

# Regex filters for Funding, VCs / funds, Corporate VCs, Accelerators, and Investment news
KEYWORDS = re.compile(
    r'\b(funding|funded|raises|raised|raising|fundraise|fundraising|pre-seed|seed round|seed funding|'
    r'series [a-f]|bridge round|venture capital|venture capitalist|vc firm|vc fund|venture fund|'
    r'corporate vc|corporate venture|cvc|flipkart ventures|angel investor|angel network|angel round|'
    r'family office|limited partners?|first close|final close|launches fund|new fund|maiden fund|'
    r'fund size|corpus|accelerator|incubator|cohort|demo day|startup program|startup programme|'
    r'y combinator|techstars|backed by|investor|investors|lead investor|valuation|unicorn)\b',
    re.IGNORECASE
)

GOOGLE_NEWS_TERMS = (
    '(funding OR raises OR investors OR "venture capital" OR accelerator OR incubator '
    'OR "seed round" OR "series a" OR "series b" OR fund OR cohort)'
)


def categorize_article(text):
    text_lower = text.lower()
    if any(term in text_lower for term in ["accelerator", "cohort", "demo day", "incubator", "startup program"]):
        return "Accelerator Program"
    elif any(term in text_lower for term in ["pre-seed", "seed", "series a", "series b", "series c", "raises", "raised", "funding"]):
        return "Startup Funding"
    elif any(term in text_lower for term in ["venture capital", "vc", "fund", "flipkart ventures", "family office", "angel"]):
        return "VC / Fund News"
    return "General Investment"


def clean_text(text):
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def get(session, url, **kwargs):
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            return resp
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
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
    articles = []
    page = 1
    while True:
        params = {
            "after": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "per_page": 100,
            "page": page,
            "orderby": "date",
            "order": "desc",
            "_fields": "date_gmt,link,title,excerpt",
            **source.get("params", {}),
        }
        resp = get(session, f"{source['base']}/wp-json/wp/v2/posts", params=params)
        if resp is None or resp.status_code != 200:
            if page == 1:
                print(f"[{source['name']}] WARNING: WordPress API returned {getattr(resp, 'status_code', 'no response')}")
            break
        posts = resp.json()
        if not posts:
            break
        for post in posts:
            articles.append({
                "date": datetime.fromisoformat(post["date_gmt"]),
                "title": clean_text(post["title"]["rendered"]),
                "summary": clean_text(post.get("excerpt", {}).get("rendered", "")),
                "link": post["link"],
            })
        total_pages = int(resp.headers.get("X-WP-TotalPages", page))
        if page >= total_pages:
            break
        page += 1
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
            if not KEYWORDS.search(slug_text(link)):
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
        query = f"site:{source['site']} {GOOGLE_NEWS_TERMS} after:{day:%Y-%m-%d} before:{end:%Y-%m-%d}"
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
                articles.append({"date": pub_date, "title": title, "summary": "", "link": entry.get("link", "")})
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


def run():
    start = get_start_date()
    print(f"Collecting articles published since {start:%Y-%m-%d %H:%M} UTC")

    sheet = setup_google_sheet()
    print(f"Connected to sheet: {sheet.spreadsheet.title} / {sheet.title}")

    # Existing links in column E, used to avoid duplicate rows
    existing_urls = set(sheet.col_values(5))
    new_rows = []

    session = requests.Session()
    session.headers.update(HEADERS)

    for source in SOURCES:
        try:
            articles = FETCHERS[source["type"]](session, source, start)
        except Exception as e:
            print(f"[{source['name']}] ERROR ({source['type']}): {e}")
            continue

        added = 0
        for article in articles:
            text = f"{article['title']} {article['summary']}"
            if not KEYWORDS.search(text):
                continue
            link = article["link"]
            if not link or link in existing_urls:
                continue
            existing_urls.add(link)
            new_rows.append([
                article["date"].strftime("%Y-%m-%d %H:%M"),
                source["name"],
                article["title"],
                categorize_article(text),
                link,
            ])
            added += 1
        print(f"[{source['name']}] ({source['type']}) fetched {len(articles)}, {added} new relevant")

    if new_rows and os.environ.get("DRY_RUN", "").lower() == "true":
        new_rows.sort(key=lambda row: row[0])
        print(f"DRY RUN: would add {len(new_rows)} rows. Sample:")
        for row in new_rows[:: max(1, len(new_rows) // 40)]:
            print("   ", " | ".join(row))
    elif new_rows:
        new_rows.sort(key=lambda row: row[0])
        sheet.append_rows(new_rows)
        print(f"Successfully added {len(new_rows)} relevant funding/VC items.")
    else:
        print("No new funding or accelerator updates found.")


if __name__ == "__main__":
    run()
