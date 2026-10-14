"""The "fast screen" of the qualify-anchors-investors skill, done from the deals in the sheet.

It only adds information; it never removes an article or an investor:
  - Investors tab: extra columns per investor (seed-stage deals, latest seed-stage deal,
    rounds led, Indian deals, deals in anchors-adjacent sectors) and a Fast screen label.
  - "To qualify" tab: funds that pass the fast screen and are not yet in the
    "Anchors Investor Qualifier" tab (the skill's results), strongest first. These are the
    ones worth running the skill on next.

The labels follow the skill's hard blockers that the news can show: not a fund (angels /
individuals are excluded by default), no deal in the last 12 months (inactive), no
seed-stage deal seen. Anything the news can't show stays "unknown" for the skill to check.
"""
import re
from datetime import datetime, timedelta

from event_rules import india_signal
from investor_extractor import _STOP, _SPLIT, _clean, _key, investor_type

NOT_FOUND = "—"
QUALIFIER_TAB = "Anchors Investor Qualifier"
TO_QUALIFY_TAB = "To qualify"

SCREEN_HEADER = [
    "Seed / pre-seed deals", "Latest seed-stage deal", "Rounds led", "Indian deals",
    "Adjacent-sector deals", "Fast screen",
]
TO_QUALIFY_HEADER = [
    "Investor / Fund", "Type", "Fast screen", "Seed / pre-seed deals", "Latest seed-stage deal", "Rounds led",
    "Indian deals", "Adjacent-sector deals", "Latest deal", "Latest deal headline", "Latest deal link",
]

# anchors: AI-native creator-advertising execution layer (ad-tech / martech, creator economy,
# B2B marketplace, SaaS, AI workflow). Sector names come from sectors.py.
ADJACENT_SECTORS = {
    "Influencer Marketing", "Creator Economy", "Social Media Management", "Social Media", "Social Commerce",
    "Marketing / AdTech", "SaaS / B2B", "AI",
}
SEED_ROUNDS = {"pre-seed", "seed", "angel", "pre-series a"}
# Publishers that only cover India: their deals count as Indian deals
INDIA_SOURCES = {
    "entrackr", "inc42", "yourstory", "vccircle", "et tech", "et tech funding", "et tech startups",
    "indian startup news", "startup story media", "entrepreneur india", "livemint", "moneycontrol",
    "business standard", "bw businessworld", "businessline", "startuptalky", "indian startup times",
    "et brandequity", "social samosa", "campaign india", "afaqs", "medianews4u", "exchange4media",
    "storyboard18", "financial express", "business today",
}
_LEAD = [
    re.compile(r"\b(?:co-)?led by\s+(?P<names>.+?)" + _STOP, re.I),
    re.compile(r"^(?P<names>[^,:]+?)\s+(?:co-)?leads?\b", re.I),
]
_USD_PER_INR = 1 / 88  # approximate; only used to tell seed-sized rounds apart
_UNIT = {"k": 1e3, "lakh": 1e5, "cr": 1e7, "crore": 1e7, "m": 1e6, "mn": 1e6, "mil": 1e6, "mln": 1e6,
         "million": 1e6, "b": 1e9, "bn": 1e9, "bln": 1e9, "billion": 1e9}


def amount_usd(text):
    """'$5 Mn' / '₹40 Cr' / 'Rs 2.5 crore' -> approximate US dollars, or None."""
    m = re.search(r"(rs\.?|inr|₹|usd|us\$|\$)?\s?(\d[\d,]*(?:\.\d+)?)\s?(mln|bln|mil|mn|million|crore|cr|bn|billion|lakh|k|m|b)?\b",
                  text or "", re.I)
    if not m or not (m.group(1) or m.group(3)):
        return None
    value = float(m.group(2).replace(",", "")) * _UNIT.get((m.group(3) or "").lower(), 1)
    rupees = (m.group(1) or "").lower() in ("rs", "rs.", "inr", "₹") or (m.group(3) or "").lower() in ("cr", "crore", "lakh")
    return value * _USD_PER_INR if rupees else value


def is_seed_stage(round_, amount):
    if (round_ or "").strip().lower() in SEED_ROUNDS:
        return True
    usd = amount_usd(amount)
    # No round named: a round of up to about $3M is seed-sized
    return not (round_ or "").strip() and usd is not None and usd <= 3e6


def lead_keys(title):
    keys = set()
    for pattern in _LEAD:
        for match in pattern.finditer(title or ""):
            for part in _SPLIT.split(match.group("names")):
                name = _clean(part)
                if name:
                    keys.add(_key(name))
    return keys


def screen(deal_rows, today=None):
    """{investor key: stats} from deal rows (single-company rows that name investors).
    Row layout: [date, source, title, category, link, company, amount, round, investors, sector]."""
    today = today or datetime.utcnow()
    stats = {}
    for row in deal_rows:
        if len(row) < 9 or not row[5] or row[8] in ("", NOT_FOUND):
            continue
        date, source, title = row[0][:10], row[1], row[2]
        sectors = {t.strip() for t in (row[9] if len(row) > 9 else "").split(";") if t.strip()}
        seed = is_seed_stage(row[7], row[6])
        indian = source.lower() in INDIA_SOURCES or india_signal(title)
        leads = lead_keys(title)
        for raw in row[8].split(";"):
            name = _clean(raw.strip())
            if not name:
                continue
            key = _key(name)
            s = stats.setdefault(key, {"seed": 0, "latest_seed": "", "led": 0, "india": 0, "adjacent": 0,
                                       "latest": "", "title": "", "link": ""})
            if seed:
                s["seed"] += 1
                s["latest_seed"] = max(s["latest_seed"], date)
            s["led"] += key in leads
            s["india"] += indian
            s["adjacent"] += bool(sectors & ADJACENT_SECTORS)
            if date >= s["latest"]:
                s["latest"], s["title"], s["link"] = date, title, row[4]
    cutoff = (today - timedelta(days=365)).strftime("%Y-%m-%d")
    for s in stats.values():
        s["active"] = s["latest"] >= cutoff
    return stats


def label(kind, s):
    """The fast-screen result for one investor (never a final decision)."""
    if kind.startswith("Angel") or kind.startswith("Family Office"):
        return "Skip by default (angel / family office)"
    if s is None:
        return "No deals seen"
    if not s["active"]:
        return "No deal in 12 months (inactive?)"
    if not s["seed"]:
        return "No seed-stage deal seen"
    if kind.startswith("Other"):
        return "Check: may not be a fund"
    if s["adjacent"] and s["india"]:
        return "Strong candidate"
    return "Candidate"


def add_screen_columns(investor_table, stats):
    """Appends SCREEN_HEADER columns to each Investors-tab row (first column: the name)."""
    for row in investor_table:
        s = stats.get(_key(row[0]))
        row += [s["seed"] if s else 0, s["latest_seed"] if s else "", s["led"] if s else 0,
                s["india"] if s else 0, s["adjacent"] if s else 0, label(row[1], s)]
    return investor_table


def to_qualify_table(investor_table, stats, qualified_names):
    """Candidates not yet assessed in the Qualifier tab, strongest first."""
    done = {_key(n) for n in qualified_names if n}
    rows = []
    for row in investor_table:
        verdict = row[-1]
        if verdict not in ("Strong candidate", "Candidate") or _key(row[0]) in done:
            continue
        s = stats[_key(row[0])]
        rows.append([row[0], row[1], verdict, s["seed"], s["latest_seed"], s["led"], s["india"], s["adjacent"],
                     s["latest"], s["title"], s["link"]])
    rows.sort(key=lambda r: (r[2] != "Strong candidate", -r[7], -r[5], -r[3], r[4] and -int(r[4].replace("-", ""))))
    return rows
