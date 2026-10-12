"""Collect India funding / investor events from event sites and news.

Each fetcher returns candidate dicts:
  {name, date (YYYY-MM-DD), city, organizer, reg_link, source, link, author}
Only upcoming events in India that match event_rules.is_event_topic are kept.

Event sites read here (reachable from GitHub's servers): Luma, Meetup, AllEvents,
Konfhub, Commudle, Headstart. Eventbrite, District, 10times, TiE and Townscript
block GitHub's servers, so the Chrome extension visits those instead.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, quote_plus, urljoin, urlparse

import feedparser

from event_rules import (find_city, find_event_date, find_organizer, india_signal, is_event_topic,
                         pick_registration_link)
from fetch_vc_news import SOURCES, clean_text, fetch_rss, fetch_wordpress, get

IST = timezone(timedelta(hours=5, minutes=30))

LUMA_CITIES = ["bengaluru", "mumbai", "delhi", "hyderabad", "pune", "chennai", "kolkata", "ahmedabad", "jaipur"]
MEETUP_CITIES = ["Bangalore", "Mumbai", "New Delhi", "Hyderabad", "Pune", "Chennai", "Kolkata", "Ahmedabad", "Gurgaon", "Noida"]
MEETUP_KEYWORDS = ["startup investors", "angel investors", "startup pitch", "founders networking", "venture capital"]
ALLEVENTS_CITIES = ["bangalore", "mumbai", "delhi", "hyderabad", "pune", "chennai", "kolkata", "ahmedabad", "gurgaon", "noida"]
ALLEVENTS_CATEGORIES = ["startup", "business"]

# Google News (India edition) searches for event coverage, last 7 days
GOOGLE_NEWS_EVENT_QUERIES = [
    '"investor meet" startups India',
    '"demo day" startups India',
    '("pitch event" OR "pitching session" OR "pitch day") startups India',
    '"startup summit" investors India',
    '"angel investors" (summit OR meet OR networking) India',
    '"venture capital" (summit OR conclave) India',
    '(accelerator OR incubator) "demo day" India',
    '("startup conclave" OR "startup expo" OR "startup mahakumbh") India',
    '"investor connect" startups India',
    '"Startup India" (summit OR roadshow OR event)',
    '"funding" roadshow startups India',
    '("e-summit" OR "esummit") startups',
    '(TiEcon OR "TiE Global Summit" OR "TiE summit")',
    '"founders" "investors" networking event India',
]

# India-focused news sources from the funding-news script, scanned for event articles
NEWS_SOURCE_NAMES = {"Entrackr", "Inc42", "YourStory", "ET Tech Startups", "ET Tech Funding", "Indian Startup News",
                     "Startup Story Media", "Entrepreneur India", "Livemint"}


def _ist_today():
    return datetime.now(IST).date()


def _candidate(name, start, text, source, link, reg_link="", city="", organizer="", author="", today=None):
    """Build a candidate, or None when it isn't an upcoming Indian investment event."""
    today = today or _ist_today()
    if not name or not start or start < today:
        return None
    if not is_event_topic(f"{name} {text}"):
        return None
    city = city or find_city(f"{name} {text}")
    if city == "Online" and not india_signal(f"{name} {text}"):
        return None
    if not city and not india_signal(f"{name} {text}"):
        return None
    return {
        "name": clean_text(name)[:250], "date": start.isoformat(), "city": city,
        "organizer": organizer or find_organizer(text), "reg_link": reg_link or link,
        "source": source, "link": link, "author": author,
    }


def _local_date(value):
    """'2026-10-14T03:00:00.000Z' / '2026-10-19' -> IST date."""
    if not value:
        return None
    value = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(value[:19])
        except ValueError:
            return None
    if parsed.tzinfo:
        parsed = parsed.astimezone(IST)
    return parsed.date()


# ---------------------------------------------------------------- schema.org JSON-LD

def jsonld_events(html):
    """All schema.org Event objects embedded in a page."""
    events = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            kind = node.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            if any(isinstance(k, str) and k.endswith("Event") for k in kinds) and node.get("startDate"):
                events.append(node)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)

    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            walk(json.loads(block.strip()))
        except ValueError:
            continue
    return events


def _ld_city(event):
    location = event.get("location") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    if location.get("@type") == "VirtualLocation":
        return "Online", ""
    address = location.get("address") or {}
    if isinstance(address, str):
        return find_city(address), address
    locality = address.get("addressLocality") or ""
    country = address.get("addressCountry") or ""
    if isinstance(country, dict):
        country = country.get("name", "")
    return (find_city(f"{locality} {address.get('addressRegion', '')}") or locality), country


def _ld_organizer(event):
    organizer = event.get("organizer") or {}
    if isinstance(organizer, list):
        organizer = organizer[0] if organizer else {}
    return organizer.get("name", "") if isinstance(organizer, dict) else str(organizer)


def events_from_jsonld(html, source, page_url, today):
    found = []
    for event in jsonld_events(html):
        city, country = _ld_city(event)
        if country and str(country).upper() not in ("IN", "IND", "INDIA") and city != "Online":
            continue
        link = urljoin(page_url, event.get("url") or page_url)
        candidate = _candidate(
            clean_text(event.get("name", "")), _local_date(event.get("startDate")),
            clean_text(event.get("description", ""))[:1500], source, link,
            city=city, organizer=_ld_organizer(event), today=today,
        )
        if candidate:
            found.append(candidate)
    return found


# ---------------------------------------------------------------- event sites

def fetch_luma(session, today):
    found = []
    for city in LUMA_CITIES:
        resp = get(session, f"https://lu.ma/{city}")
        if resp is None or resp.status_code != 200:
            print(f"[Luma] WARNING: {city} page returned {getattr(resp, 'status_code', 'no response')}")
            continue
        place = re.search(r'"(discplace-[A-Za-z0-9]+)"', resp.text)
        if not place:
            continue
        cursor = None
        for _ in range(5):  # up to 250 events per city
            url = (f"https://api.lu.ma/discover/get-paginated-events?discover_place_api_id={place.group(1)}"
                   f"&pagination_limit=50" + (f"&pagination_cursor={quote(cursor)}" if cursor else ""))
            api = get(session, url)
            if api is None or api.status_code != 200:
                break
            data = api.json()
            for entry in data.get("entries", []):
                event = entry.get("event", {})
                geo = event.get("geo_address_info") or {}
                hosts = entry.get("hosts") or []
                organizer = (entry.get("calendar") or {}).get("name") or (hosts[0].get("name") if hosts else "")
                is_online = event.get("location_type") == "online"
                if not is_online and geo.get("country_code") and geo["country_code"] != "IN":
                    continue  # discover pages also list popular events abroad
                candidate = _candidate(
                    event.get("name", ""), _local_date(event.get("start_at")), "", "Luma",
                    f"https://lu.ma/{event.get('url', '')}",
                    city="Online" if is_online else (find_city(geo.get("city", "")) or geo.get("city") or city.title()),
                    organizer=organizer, today=today,
                )
                if candidate:
                    found.append(candidate)
            cursor = data.get("next_cursor")
            if not data.get("has_more") or not cursor:
                break
            time.sleep(0.5)
    return found


def fetch_meetup(session, today):
    found = []
    for city in MEETUP_CITIES:
        for keyword in MEETUP_KEYWORDS:
            url = (f"https://www.meetup.com/find/?keywords={quote_plus(keyword)}"
                   f"&location=in--{quote(city)}&source=EVENTS")
            resp = get(session, url)
            if resp is None or resp.status_code != 200:
                print(f"[Meetup] WARNING: {city}/{keyword} returned {getattr(resp, 'status_code', 'no response')}")
                continue
            found += events_from_jsonld(resp.text, "Meetup", url, today)
            time.sleep(0.5)
    return found


def fetch_allevents(session, today):
    found = []
    for city in ALLEVENTS_CITIES:
        for category in ALLEVENTS_CATEGORIES:
            url = f"https://allevents.in/{city}/{category}"
            resp = get(session, url)
            if resp is None or resp.status_code != 200:
                continue
            found += events_from_jsonld(resp.text, "AllEvents", url, today)
            time.sleep(0.5)
    return found


def fetch_konfhub(session, today):
    resp = get(session, "https://manage-api.konfhub.com/featured-events")
    if resp is None or resp.status_code != 200:
        print(f"[Konfhub] WARNING: returned {getattr(resp, 'status_code', 'no response')}")
        return []
    found = []
    for event in resp.json().get("featuredEvents", []):
        if event.get("country") and event["country"] != "India":
            continue
        city = "Online" if event.get("is_virtual") else (find_city(event.get("city") or "") or event.get("city") or "")
        candidate = _candidate(
            event.get("name", ""), _local_date(event.get("start_date")), event.get("venue") or "", "Konfhub",
            event.get("featured_url") or f"https://konfhub.com/{event.get('event_url', '')}",
            city=city, today=today,
        )
        if candidate:
            found.append(candidate)
    return found


def fetch_commudle(session, today):
    resp = get(session, "https://json.commudle.com/api/v2/events/public?when=future&limit=100")
    if resp is None or resp.status_code != 200:
        print(f"[Commudle] WARNING: returned {getattr(resp, 'status_code', 'no response')}")
        return []
    found = []
    for item in resp.json().get("data", {}).get("page", []):
        event = item.get("data", {})
        community = event.get("kommunity") or {}
        link = f"https://www.commudle.com/communities/{event.get('kommunity_slug', '')}/events/{event.get('slug', '')}"
        candidate = _candidate(
            event.get("name", ""), _local_date(event.get("start_time")), clean_text(event.get("description", ""))[:1500],
            "Commudle", link, organizer=community.get("name", "") if isinstance(community, dict) else "", today=today,
        )
        if candidate:
            found.append(candidate)
    return found


def fetch_headstart(session, today):
    query = {"sort": {"starts_at": "desc"}, "limit": 50, "page": 1, "where": {"status": "published"}}
    resp = get(session, "https://www.headstart.in/_levo/cdn/api/v1/event/event/query?query=" + quote(json.dumps(query)))
    if resp is None or resp.status_code != 200:
        print(f"[Headstart] WARNING: returned {getattr(resp, 'status_code', 'no response')}")
        return []
    found = []
    for event in resp.json().get("content", {}).get("data", []):
        text = clean_text(event.get("description", ""))[:1500]
        city = "Online" if event.get("kind") == "online" else ""
        candidate = _candidate(
            event.get("title", ""), _local_date(event.get("starts_at")), text, "Headstart",
            f"https://www.headstart.in/events/{event.get('slug', '')}",
            reg_link=event.get("register_url") or event.get("external_url") or "", city=city,
            organizer="Headstart Network", today=today,
        )
        if candidate:
            found.append(candidate)
    return found


# ---------------------------------------------------------------- news

def resolve_google_news(session, link):
    """news.google.com/rss/articles/... -> publisher URL (None if Google refuses)."""
    art_id = urlparse(link).path.rsplit("/", 1)[-1]
    page = get(session, f"https://news.google.com/rss/articles/{art_id}")
    if page is None or page.status_code != 200:
        return None
    sig = re.search(r'data-n-a-sg="([^"]+)"', page.text)
    stamp = re.search(r'data-n-a-ts="([^"]+)"', page.text)
    if not (sig and stamp):
        return None
    inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                            "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], art_id, int(stamp.group(1)), sig.group(1)]
    payload = [[["Fbv4je", json.dumps(inner), None, "generic"]]]
    try:
        resp = session.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                            data="f.req=" + quote(json.dumps(payload)), timeout=30)
        for line in resp.text.split("\n"):
            if line.startswith('[["wrb.fr"'):
                return json.loads(json.loads(line)[0][2])[1]
    except Exception:
        return None
    return None


def fetch_article(session, url):
    """(text, links) from an article page: description + opening paragraphs, and body links."""
    resp = get(session, url)
    if resp is None or resp.status_code != 200:
        return "", []
    page = resp.text
    body = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", page)
    parts = re.findall(r'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="([^"]*)"', page)
    parts += [p for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body) if len(clean_text(p)) > 40][:25]
    links = [urljoin(url, href) for href in re.findall(r'<a[^>]+href="([^"#]+)"', body)]
    return " ".join(clean_text(p) for p in parts)[:8000], links


def _news_candidate(session, title, summary, link, publisher, published, today):
    """Read the article to find the event date, city and registration link."""
    if not is_event_topic(f"{title} {summary}"):
        return None
    url = link
    if "news.google.com" in link:
        url = resolve_google_news(session, link) or link
    text, links = ("", []) if "news.google.com" in url else fetch_article(session, url)
    full = f"{title}. {summary} {text}"
    # News covers events worldwide: keep only those in an Indian city, or India-related in the headline
    city = find_city(full)
    if not ((city and city != "Online") or india_signal(title)):
        return None
    start = find_event_date(full, published, today=today)
    candidate = _candidate(title, start, full, f"News - {publisher}", url,
                           reg_link=pick_registration_link(links), today=today)
    return candidate


def fetch_google_news_events(session, today):
    entries = []
    for query in GOOGLE_NEWS_EVENT_QUERIES:
        url = f"https://news.google.com/rss/search?q={quote_plus(query + ' when:7d')}&hl=en-IN&gl=IN&ceid=IN:en"
        resp = get(session, url)
        if resp is None or resp.status_code != 200:
            continue
        for entry in feedparser.parse(resp.content).entries:
            if not entry.get("published"):
                continue
            title = clean_text(entry.get("title", ""))
            publisher = entry.get("source", {}).get("title", "") or "Google News"
            if title.endswith(f" - {publisher}"):
                title = title[: -len(publisher) - 3]
            published = parsedate_to_datetime(entry.published).astimezone(IST).date()
            entries.append((title, "", entry.get("link", ""), publisher, published))
        time.sleep(1)
    unique = {e[0].lower(): e for e in entries}.values()
    relevant = [e for e in unique if is_event_topic(e[0])]
    print(f"[Google News] {len(entries)} results, {len(relevant)} look like events")
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda e: _news_candidate(session, *e, today), relevant))
    return [r for r in results if r]


def fetch_news_site_events(session, today):
    start = datetime.utcnow() - timedelta(days=7)
    articles = []
    for source in SOURCES:
        if source["name"] not in NEWS_SOURCE_NAMES or source["type"] not in ("rss", "wordpress"):
            continue
        try:
            fetched = (fetch_rss if source["type"] == "rss" else fetch_wordpress)(session, source, start)
        except Exception as e:
            print(f"[{source['name']}] ERROR: {e}")
            continue
        for article in fetched:
            if is_event_topic(f"{article['title']} {article['summary']}"):
                published = article["date"].replace(tzinfo=timezone.utc).astimezone(IST).date()
                articles.append((article["title"], article["summary"], article["link"], source["name"], published))
    print(f"[News sites] {len(articles)} articles look like events")
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda a: _news_candidate(session, *a, today), articles))
    return [r for r in results if r]


FETCHERS = [
    ("Luma", fetch_luma),
    ("Meetup", fetch_meetup),
    ("AllEvents", fetch_allevents),
    ("Konfhub", fetch_konfhub),
    ("Commudle", fetch_commudle),
    ("Headstart", fetch_headstart),
    ("Google News", fetch_google_news_events),
    ("News sites", fetch_news_site_events),
]
