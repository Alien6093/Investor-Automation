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
_MONEY = re.compile(
    r"\b(invest(?:or|ors|ment|ments|ing)?|angels?|vcs?|venture capital(?:ists?)?|funding|fundrais(?:e|ing)|"
    r"pitch(?:es|ing)?|pre-seed|seed fund|accelerators?|incubators?|grants?|capital)\b",
    re.I,
)
_EVENT_NOUN = re.compile(
    r"\b(meet|meetup|meet-up|summit|conclave|conference|event|mixer|networking|session|webinar|workshop|masterclass|"
    r"expo|fest|festival|bootcamp|boot camp|roadshow|road show|connect|forum|huddle|roundtable|round table|"
    r"symposium|showcase|convention|breakfast|brunch|open house|info session|cohort day)\b",
    re.I,
)
_STARTUP = re.compile(r"\b(start-?ups?|founders?|entrepreneurs?)\b", re.I)
_STARTUP_EVENT = re.compile(
    r"\b(networking|mixer|meetup|meet-up|summit|conclave|expo|showcase|pitch|bootcamp|roadshow|fest|connect|"
    r"office hours|open house)\b",
    re.I,
)
# Listed-company / stock-market / jobs noise ("institutional investor meet", "job fair")
_EXCLUDE = re.compile(
    r"\b(shares?|stocks?|nse|bse|sensex|nifty|ipo|listed|earnings|quarterly results|q[1-4] (?:results|fy)|"
    r"analysts?|institutional investors?|concall|conference call|dividend|mutual funds?|sip|trading|traders?|"
    r"forex|crypto(?:currency)?|bitcoin|job fair|hiring|recruitment|placement drive|walk-?in|real estate|"
    r"property expo|wedding|retail investors?|wealth|personal finance|financial freedom|options|futures)\b",
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
    r"kerala startup mission|startuptn|iit|iim|iisc|tie [a-z]+)\b|₹|\brs\.?\s?\d)",
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


def india_signal(text):
    return bool(_INDIA.search(text or "")) or any(p.search(text or "") for _, p in _CITY_RE)


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
_DEADLINE = re.compile(r"(deadline|apply by|applications? close|last date|register by|registrations? close|before|closes|till|until|due)\W*(?:\w+\W+){0,2}$", re.I)


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
            if _DEADLINE.search(before):
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
            if year:
                found_date = _make_date(int(year), month, day)
            else:
                found_date = _make_date(ref.year, month, day)
                # "5 Jan" written in December means next January
                if found_date and found_date < ref - timedelta(days=30):
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
    r"typeform\.com|tally\.so|airtable\.com|jotform\.com|zoom\.us/(?:webinar|meeting)|headstart\.in/events|"
    r"bit\.ly|linktr\.ee)",
    re.I,
)


def find_organizer(text):
    match = _ORGANIZER.search(text or "")
    return match.group(1).strip(" .,'’") if match else ""


def pick_registration_link(links):
    for link in links:
        if REGISTRATION_DOMAINS.search(link):
            return link
    return ""


def name_key(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())[:120]


def link_key(link):
    link = (link or "").strip().lower()
    link = re.sub(r"^https?://(www\.)?", "", link)
    link = re.sub(r"[?#].*$", "", link)
    return link.rstrip("/")
