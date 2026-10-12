"""Rules for spotting India-only funding / investor events in free text.

Used for event-site listings, news articles and (mirrored in the Chrome extension)
LinkedIn / X / Reddit posts:
  - is_event_topic(text): funding events, investor meets, demo days, pitch events,
    startup-investor networking, accelerator / government startup events
  - india_signal(text) / find_city(text): India-only filter and the City / Online cell
  - find_event_date(text, ref): the first upcoming date mentioned in the text
"""
import re
from datetime import date, timedelta
from urllib.parse import parse_qsl, urlsplit

# ---------------------------------------------------------------- topic

# Phrases that on their own mark an investment event
_DIRECT = re.compile(
    r"\b(investors?[\s-]+(?:meet|meetup|meet-up|connect|day|summit|conclave|networking|mixer|forum|roundtable)|"
    r"demo[\s-]?days?|pitch(?:ing)?[\s-]+(?:day|night|event|session|fest|competition|battle|summit|cafe|deck clinic)|"
    r"startup pitch|reverse pitch|office hours|fundrais(?:e|ing)[\s-]+(?:workshop|bootcamp|masterclass|summit|session)|"
    r"funding[\s-]+(?:summit|conclave|connect|fair|meet|event|roadshow)|angel[\s-]+(?:investors?[\s-]+)?(?:meet|summit|network meet)|"
    r"vc[\s-]+(?:meet|connect|summit|networking|mixer)|venture capital (?:summit|conclave|forum)|"
    r"e-?summit|tiecon|startup mahakumbh|startup india (?:summit|roadshow|innovation week|event)|"
    r"founders?[\s-]+(?:and|&|x|meet)[\s-]+investors?|investors?[\s-]+(?:and|&|x)[\s-]+founders?)\b",
    re.I,
)
# Money words and event nouns only count together. Generic words such as "connect",
# "meet", "session" alone or "pitch" / "capital" are left out: they appear in ordinary text.
_MONEY = re.compile(
    r"\b(invest(?:or|ors|ment|ments|ing)?|angels?|vcs?|venture capital(?:ists?)?|funding|fundrais(?:e|ing)|"
    r"pre-seed|seed fund|accelerators?|incubators?|grants?)\b",
    re.I,
)
_EVENT_NOUN = re.compile(
    r"\b(meetup|meet-up|summit|conclave|conference|event|mixer|networking|webinar|workshop|masterclass|"
    r"expo|fest|festival|bootcamp|boot camp|roadshow|road show|forum|huddle|roundtable|round table|"
    r"symposium|showcase|convention|breakfast|brunch|open house|info session|cohort day)\b",
    re.I,
)
_STARTUP = re.compile(r"\b(start-?ups?|founders?|entrepreneurs?)\b", re.I)
_STARTUP_EVENT = re.compile(
    r"\b(networking|mixer|meetup|meet-up|summit|conclave|expo|showcase|bootcamp|roadshow|fest|"
    r"office hours|open house)\b",
    re.I,
)
# Stock-market, jobs and property events. Phrases, not single words: "share", "options",
# "listed" or "hiring" alone appear in normal startup text ("Excited to share ...").
_EXCLUDE = re.compile(
    r"\b(share price|shares? of|stock (?:market|price|split)s?|stocks? to (?:buy|watch)|nse|bse|sensex|nifty|"
    r"ipo (?:subscription|allotment|gmp|listing|price band|opens|closes)|listing gains|earnings call|"
    r"quarterly results|q[1-4] (?:results|fy\d*)|analysts? meet|concall|"
    r"conference call|dividends?|mutual funds?|sip returns|intraday|trading (?:session|tips|strategy|course)|forex|"
    r"crypto(?:currency)?|bitcoin|job fair|hiring drive|walk-?in interviews?|placement drive|recruitment drive|"
    r"real estate|property expo|wedding|retail investors?|wealth management|personal finance|financial freedom|"
    r"options trading|futures (?:and|&) options|f&o)\b",
    re.I,
)


def is_event_topic(text):
    if not text or _EXCLUDE.search(text):
        return False
    if _DIRECT.search(text):
        return True
    if _MONEY.search(text) and _EVENT_NOUN.search(text):
        return True
    return bool(_STARTUP.search(text) and _STARTUP_EVENT.search(text))


# ---------------------------------------------------------------- India / city

# Canonical city name -> spellings
CITIES = {
    "Bengaluru": ["bengaluru", "bangalore", "blr"],
    "Mumbai": ["mumbai", "bombay", "navi mumbai", "thane"],
    "Delhi NCR": ["delhi", "new delhi", "ncr", "gurugram", "gurgaon", "noida", "greater noida", "faridabad", "ghaziabad"],
    "Hyderabad": ["hyderabad", "secunderabad"],
    "Pune": ["pune"],
    "Chennai": ["chennai", "madras"],
    "Kolkata": ["kolkata", "calcutta"],
    "Ahmedabad": ["ahmedabad", "gandhinagar", "gift city"],
    "Jaipur": ["jaipur"],
    "Kochi": ["kochi", "cochin"],
    "Thiruvananthapuram": ["thiruvananthapuram", "trivandrum"],
    "Chandigarh": ["chandigarh", "mohali"],
    "Indore": ["indore"],
    "Bhopal": ["bhopal"],
    "Bhubaneswar": ["bhubaneswar"],
    "Coimbatore": ["coimbatore"],
    "Lucknow": ["lucknow"],
    "Goa": ["goa", "panaji"],
    "Nagpur": ["nagpur"],
    "Surat": ["surat"],
    "Vadodara": ["vadodara", "baroda"],
    "Visakhapatnam": ["visakhapatnam", "vizag"],
    "Mysuru": ["mysuru", "mysore"],
    "Mangaluru": ["mangaluru", "mangalore"],
    "Patna": ["patna"],
    "Guwahati": ["guwahati"],
    "Dehradun": ["dehradun"],
    "Ranchi": ["ranchi"],
    "Raipur": ["raipur"],
    "Nashik": ["nashik"],
    "Madurai": ["madurai"],
    "Vijayawada": ["vijayawada"],
    "Kanpur": ["kanpur"],
    "Ludhiana": ["ludhiana"],
    "Amritsar": ["amritsar"],
    "Varanasi": ["varanasi"],
    "Agra": ["agra"],
    "Meerut": ["meerut"],
    "Jodhpur": ["jodhpur"],
    "Udaipur": ["udaipur"],
    "Rajkot": ["rajkot"],
    "Hubballi": ["hubli", "hubballi"],
    "Belagavi": ["belgaum", "belagavi"],
    "Tiruchirappalli": ["trichy", "tiruchirappalli"],
    "Kozhikode": ["kozhikode", "calicut"],
    "Thrissur": ["thrissur"],
    "Jammu": ["jammu"],
    "Srinagar": ["srinagar"],
    "Shimla": ["shimla"],
    "Aurangabad": ["aurangabad", "chhatrapati sambhajinagar"],
    "Gwalior": ["gwalior"],
    "Jabalpur": ["jabalpur"],
    "Prayagraj": ["prayagraj", "allahabad"],
    "Warangal": ["warangal"],
    "Tirupati": ["tirupati"],
    "Puducherry": ["puducherry", "pondicherry"],
}
_CITY_RE = [(name, re.compile(r"\b(?:" + "|".join(re.escape(s) for s in spellings) + r")\b", re.I))
            for name, spellings in CITIES.items()]
_INDIA = re.compile(
    r"(\b(?:india|indian|indians|bharat|inr|lakhs?|crores?|startup india|dpiit|meity|nasscom|t-hub|ksum|"
    r"kerala startup mission|startuptn|iit|iim|iisc)\b|₹|\brs\.?\s?\d)",
    re.I,
)
_TIE = re.compile(r"\bTiE\b")  # the TiE network; case-sensitive so "tie up" doesn't count
# Places abroad: an event there isn't an India event even when "Indian founders" are mentioned
_FOREIGN = re.compile(
    r"\b(san francisco|bay area|silicon valley|new york|nyc|london|dubai|abu dhabi|uae|singapore|berlin|paris|"
    r"toronto|vancouver|sydney|melbourne|riyadh|saudi|doha|qatar|boston|seattle|austin|los angeles|tokyo|"
    r"hong kong|jakarta|kuala lumpur|bangkok|nairobi|lagos|tel aviv|amsterdam|stockholm|zurich|munich|"
    r"kathmandu|dhaka|colombo|karachi|lahore)\b",
    re.I,
)
_ONLINE = re.compile(r"\b(online|virtual(?:ly)?|webinar|zoom|google meet|livestream|live stream|ms teams)\b", re.I)


def find_city(text):
    """First Indian city named in the text, else 'Online' for virtual events, else ''."""
    best = None
    for name, pattern in _CITY_RE:
        match = pattern.search(text or "")
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), name)
    if best:
        return best[1]
    return "Online" if _ONLINE.search(text or "") else ""


def event_index(text):
    """Index of the first event phrase in the text (to find the event's city), else -1."""
    for pattern in (_DIRECT, _EVENT_NOUN, _STARTUP_EVENT):
        match = pattern.search(text or "")
        if match:
            return match.start()
    return -1


def find_city_near(text, index=-1):
    """The Indian city mentioned closest to `index` (the event phrase); first city when index < 0."""
    if index < 0:
        return find_city(text)
    best = None
    for name, pattern in _CITY_RE:
        for match in pattern.finditer(text or ""):
            distance = abs(match.start() - index)
            if best is None or distance < best[0]:
                best = (distance, name)
    if best:
        return best[1]
    return "Online" if _ONLINE.search(text or "") else ""


def india_signal(text):
    return bool(_INDIA.search(text or "") or _TIE.search(text or "")) or any(p.search(text or "") for _, p in _CITY_RE)


def is_india_event(text, india_known=False):
    """An event in India: an Indian city is named, or India is mentioned and no place abroad is.
    When both an Indian city and a place abroad are named, the one nearest the event phrase
    decides ("Calling Mumbai startups: summit in Dubai on 5 Nov" is abroad)."""
    text = text or ""
    city = find_city(text)
    foreign_at = [m.start() for m in _FOREIGN.finditer(text)]
    if not foreign_at:
        return bool(city and city != "Online") or india_known or india_signal(text)
    if not city or city == "Online":
        return False
    at = max(0, event_index(text))
    city_at = [m.start() for _, pattern in _CITY_RE for m in pattern.finditer(text)]
    nearest = lambda positions: min(abs(i - at) for i in positions)
    return nearest(city_at) < nearest(foreign_at)


# ---------------------------------------------------------------- dates

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_ORD = r"(?:st|nd|rd|th)?"
_DATE_PATTERNS = [
    # "5-6 November 2026", "5th & 6th Nov"  -> first day
    ("dmy", re.compile(rf"\b(\d{{1,2}}){_ORD}\s*(?:-|–|—|to|&|and)\s*\d{{1,2}}{_ORD}\s+(?:of\s+)?{_MONTH}\b\.?,?\s*(\d{{4}})?", re.I)),
    # "5 November 2026", "5th of Nov"
    ("dmy", re.compile(rf"\b(\d{{1,2}}){_ORD}\s+(?:of\s+)?{_MONTH}\b\.?,?\s*(\d{{4}})?", re.I)),
    # "November 5, 2026", "Nov 5-6", "Oct 13–24"
    ("mdy", re.compile(rf"\b{_MONTH}\b\.?\s+(\d{{1,2}}){_ORD}(?!\d)(?:\s*(?:-|–|—|to)\s*\d{{1,2}}{_ORD})?,?\s*(\d{{4}})?", re.I)),
    # "2026-11-05"
    ("iso", re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")),
    # "05/11/2026", "5.11.26" (Indian day-first)
    ("num", re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4}|\d{2})\b")),
]
# A date right after these words is a deadline, not the event day
# The words between the deadline phrase and the date may not contain digits or separators,
# so "Register by 25 Oct; summit 2 Nov" keeps 2 Nov and "10 AM till 1 PM on 25 Oct" keeps 25 Oct.
_DEADLINE = re.compile(
    r"\b(deadline|apply by|applications? (?:close|closes|closing|due)|last (?:date|day)|register by|registrations? close|"
    r"submit by|pitch by)[^\w;|.\n]*(?:[^\W\d]+[^\w;|.\n]+){0,3}$",
    re.I,
)
_DEADLINE_RIGHT_BEFORE = re.compile(r"\b(?:by|before|till|until|due)\s+(?:the\s+)?$", re.I)


def _make_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_dates(text, ref):
    """All dates mentioned in the text (year inferred from `ref` when missing)."""
    found = []
    for kind, pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text or ""):
            before = (text or "")[max(0, match.start() - 30):match.start()]
            if _DEADLINE.search(before) or _DEADLINE_RIGHT_BEFORE.search(before):
                continue
            year = None
            if kind == "dmy":
                day, month, year = int(match.group(1)), _MONTHS[match.group(2)[:3].lower()], match.group(3)
            elif kind == "mdy":
                month, day, year = _MONTHS[match.group(1)[:3].lower()], int(match.group(2)), match.group(3)
            elif kind == "iso":
                year, month, day = match.group(1), int(match.group(2)), int(match.group(3))
            else:
                day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
                if len(year) == 2:
                    year = "20" + year
            # A 4-digit number after a date is only a year when it is close to the reference year
            if year and abs(int(year) - ref.year) > 2:
                year = None
            if year:
                found_date = _make_date(int(year), month, day)
            else:
                found_date = _make_date(ref.year, month, day)
                # "5 Jan" written in December means next January. A date only weeks back
                # ("held on 5 September", written in October) stays in the past.
                if found_date and found_date < ref - timedelta(days=180):
                    found_date = _make_date(ref.year + 1, month, day)
            if found_date:
                found.append((match.start(), found_date))
    return [d for _, d in sorted(found)]


def find_event_date(text, ref, today=None, horizon_days=365):
    """Earliest date in the text that is today or later (and within a year), else None."""
    today = today or ref
    upcoming = [d for d in find_dates(text, ref) if today <= d <= today + timedelta(days=horizon_days)]
    return min(upcoming) if upcoming else None


# ---------------------------------------------------------------- misc

_ORGANIZER = re.compile(r"\b(?:organi[sz]ed|hosted|presented|powered|curated)\s+by\s+([A-Z][\w&.'’-]*(?:\s+[A-Z0-9][\w&.'’-]*){0,5})")

REGISTRATION_DOMAINS = re.compile(
    r"(lu\.ma|luma\.com|eventbrite\.|konfhub\.com|townscript\.com|meetup\.com|allevents\.in|district\.in|insider\.in|"
    r"commudle\.com|hasgeek\.com|unstop\.com|devfolio\.co|10times\.com|docs\.google\.com/forms|forms\.gle|"
    r"typeform\.com|tally\.so|airtable\.com|jotform\.com|zoom\.us/(?:webinar|meeting)|headstart\.in/events)",
    re.I,
)


def find_organizer(text):
    match = _ORGANIZER.search(text or "")
    return match.group(1).strip(" .,'’") if match else ""


def is_event_specific_link(link):
    """A link that identifies one event (usable as a merge key). Profile / organiser pages
    (linktr.ee, a Meetup group, an Eventbrite organiser, a Luma calendar) and unresolved
    short links can stand for many events. Mirrors isEventSpecificLink in the extension."""
    key = link_key(link)
    if not key:
        return False
    if re.match(r"(linktr\.ee|bit\.ly|lnkd\.in|t\.co|tinyurl\.com|rb\.gy|shorturl\.at)/", key):
        return False
    if key.startswith("meetup.com/") and not re.search(r"/events/\d+", key):
        return False
    if key.startswith("eventbrite.com/o/"):
        return False
    if re.match(r"lu\.ma/(calendar|user|u)/", key):
        return False
    # A site's home page or an event listing stands for many events
    if "/" not in key:
        return False
    if re.match(r"(eventbrite\.com/d/|headstart\.in/events$|district\.in/events$|allevents\.in/[^/]+/[^/]+$|"
                r"10times\.com/[a-z-]+/[a-z-]+$|tie\.org/events$|townscript\.com/in/)", key):
        return False
    return True


def pick_registration_link(links):
    for link in links:
        if REGISTRATION_DOMAINS.search(link) and is_event_specific_link(link):
            return link
    return ""


def name_key(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())[:120]


# Different hosts for the same pages
_HOST_ALIASES = [
    (re.compile(r"^luma\.com$"), "lu.ma"),
    (re.compile(r"^eventbrite\.(?:co\.in|co\.uk|com\.au|ca|ie|de|fr|es|nl|sg)$"), "eventbrite.com"),
    (re.compile(r"^twitter\.com$"), "x.com"),
]
# Tracking parameters that don't change which page a link opens
_TRACKING_PARAM = re.compile(r"^(utm_.*|fbclid|gclid|trk|trackingid|ref|refid|si|s|usp|aff|_ga)$", re.I)


def link_key(link, keep_query=False):
    """Normalised link used to match rows: no scheme, www./m., tracking or trailing slash.
    keep_query keeps the remaining query. Mirrors linkKey in the extension's lib/rules.js."""
    raw = (link or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw if re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I) else f"https://{raw}")
    host = (parsed.hostname or "").lower()
    host = re.sub(r"^(?:www|m|mobile)\.", "", host)
    for pattern, alias in _HOST_ALIASES:
        if pattern.match(host):
            host = alias
    query = ""
    if keep_query:
        params = sorted((k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not _TRACKING_PARAM.match(k))
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params)
    return f"{host}{parsed.path.rstrip('/')}{query}".lower()
