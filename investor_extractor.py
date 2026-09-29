"""Pull investor / fund / accelerator names out of funding headlines.

Headlines follow a handful of patterns ("X raises $5 Mn led by Y",
"Y leads Series A in X", "Y-backed X", "Y announces first close of Fund II"),
so simple patterns catch most names without needing an LLM.
"""
import re

# Words that end an investor-name phrase
_STOP = (
    r"(?:\s+(?:to|for|as|at|in|into|amid|with|via|on|after|ahead|while|that|who|which|"
    r"and others|among others|others|existing investors|other investors|valuing|valuation)\b"
    r"|\s+[-–—|:;(]|[?!;:(]|\.$|$)"
)

_PATTERNS = [
    # "... led by Peak XV and Accel" / "... co-led by Z47"
    re.compile(r"\b(?:co-)?led by\s+(?P<names>.+?)" + _STOP, re.I),
    # "... backed by Rainmatter" / "... with participation from Blume"
    re.compile(r"\b(?:backed by|participation (?:from|of))\s+(?P<names>.+?)" + _STOP, re.I),
    # "raises Rs 100 Cr from ValueQuest Fund II" (only in funding headlines)
    re.compile(r"\b(?:raises|raised|secures|bags|gets|nets|receives|pockets)\b.*?\bfrom\s+(?P<names>.+?)" + _STOP, re.I),
    # "Fireside Ventures leads $5 Mn Series A round in CHOSEN"
    re.compile(r"^(?P<names>[^,:]+?)\s+(?:co-)?leads?\b", re.I),
    # "Aum Ventures announces first close of ... Fund II" / "Udtara Ventures launches fund"
    re.compile(r"^(?P<names>[^,:]+?)\s+(?:announces|marks|achieves|hits|launches|unveils|rolls out|floats|closes|"
               r"sets up|debuts|kicks off)\b.*?\b(?:fund|close|cohort|accelerator|programme|program)\b", re.I),
    # "Peak XV's Surge programme selects 18 startups for 12th cohort"
    re.compile(r"^(?P<names>[^,:]+?)\s+(?:selects|picks|announces|unveils|opens applications)\b.*?\b(?:cohort|batch|startups for)\b", re.I),
    # "Aramco Ventures invests in ..." / "Blume Ventures backs ..."
    re.compile(r"^(?P<names>[^,:]+?)\s+(?:invests|backs|bets on|doubles down on|picks up stake)\b", re.I),
]

# "Peak XV-backed Mosaic", "Virat Kohli-Backed WROGN"
_BACKED_PREFIX = re.compile(r"((?:[A-Z0-9][\w.&']*\s+){0,3}[A-Z0-9][\w.&']*)-backed\b", re.I)

_SPLIT = re.compile(r"\s*(?:,|\band\b|&|\bplus\b|/)\s*", re.I)

_NOT_NAMES = {
    "others", "investors", "existing investors", "angel investors", "angels", "clutch of investors",
    "family offices", "hnis", "high net worth individuals", "a clutch of investors", "vcs", "ceos",
    "founders", "its founders", "the founders", "existing backers", "new investors", "strategic investors",
    "a group of investors", "a clutch of angel investors", "multiple investors", "several investors",
    "domestic investors", "global investors", "institutional investors", "the company", "it", "fund",
    "the fund", "startup", "startups", "india", "us", "government", "govt", "series a", "series b",
    "seed round", "funding", "round", "new fund", "investment", "series c", "pre-series a", "debt",
}

_LEADING_JUNK = re.compile(
    r"^(?:its|the|a|an|existing investor|existing investors|investor|investors|vc firm|vc|"
    r"venture capital firm|investment firm|fund|global|us-based|india-based|singapore-based|"
    r"early-stage vc|early stage vc|early-stage investor|clutch of|new investor)\s+", re.I
)
_AMOUNT = re.compile(r"(?:rs\.?|inr|usd|us\$|\$|₹|€|£)\s?[\d.,]+|\b[\d.,]+\s?(?:mn|million|cr|crore|bn|billion|lakh|k)\b", re.I)


def _clean(name):
    name = name.strip(" '\"‘’“”.,-–—")
    name = re.sub(r"^(?:and|&)\s+", "", name, flags=re.I)
    for _ in range(2):
        name = _LEADING_JUNK.sub("", name)
    name = re.sub(r"\s+(?:programme|program|accelerator program(?:me)?)$", "", name, flags=re.I)
    name = re.sub(r"[’']s$", "", name).strip(" '\"‘’“”,-")
    if not name or _AMOUNT.search(name):
        return None
    # Must look like a proper name: some capital letter or digit (allows "pi Ventures")
    if name.lower() in _NOT_NAMES or not re.search(r"[A-Z0-9]", name):
        return None
    if len(name) < 2 or len(name) > 60 or len(name.split()) > 6:
        return None
    return name


def extract_investors(title):
    """Return investor / fund / accelerator names mentioned in a headline."""
    found = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(title):
            for part in _SPLIT.split(match.group("names")):
                name = _clean(part)
                if name and name not in found:
                    found.append(name)
    for match in _BACKED_PREFIX.finditer(title):
        # Only keep the capitalised words directly before "-backed"
        words = match.group(1).split()
        tail = []
        for word in reversed(words):
            if not re.match(r"[A-Z0-9]", word):
                break
            tail.insert(0, word)
        name = _clean(" ".join(tail))
        if name and name not in found:
            found.append(name)
    return found


def investor_type(name):
    lower = name.lower()
    if re.search(r"accelerator|incubator|y combinator|techstars|surge|launchpad|startup program|500 global|antler", lower):
        return "Accelerator / Incubator"
    if "family office" in lower:
        return "Family Office"
    if re.search(r"angel|network|syndicate|shark tank", lower):
        return "Angel / Network"
    if re.search(r"ventures?|capital|partners|vc\b|fund|investments?|equity|advisors|asset|holdings|"
                 r"\bpe\b|sequoia|accel|peak xv|blume|elevation|lightspeed|nexus|matrix|kalaari|"
                 r"a16z|bessemer|tiger global|softbank|general catalyst|iron pillar|3one4|stellaris|chiratae|"
                 r"rainmatter|z47|ajvc|pi ventures|fireside|verlinvest|rebalance|oister|360 one|temasek|gic|ifc", lower):
        return "VC / PE Fund"
    return "Other (Corporate / Individual)"


def build_investor_table(rows):
    """rows: sheet rows [date, source, title, category, link]. Returns rows for the Investors tab."""
    investors = {}
    for row in rows:
        if len(row) < 5 or not row[2]:
            continue
        date, source, title, _category, link = row[:5]
        for name in extract_investors(title):
            key = re.sub(r"[^a-z0-9]", "", name.lower())
            entry = investors.setdefault(key, {
                "name": name, "mentions": 0, "first": date, "latest": date,
                "title": title, "link": link, "sources": set(),
            })
            entry["mentions"] += 1
            entry["sources"].add(source)
            if date < entry["first"]:
                entry["first"] = date
            if date >= entry["latest"]:
                entry["latest"], entry["title"], entry["link"] = date, title, link

    table = []
    for entry in sorted(investors.values(), key=lambda e: (-e["mentions"], e["name"].lower())):
        table.append([
            entry["name"],
            investor_type(entry["name"]),
            entry["mentions"],
            entry["first"],
            entry["latest"],
            entry["title"],
            entry["link"],
            ", ".join(sorted(entry["sources"])),
        ])
    return table


INVESTOR_HEADER = [
    "Investor / Fund", "Type", "Mentions", "First Seen", "Latest Mention",
    "Latest Headline", "Latest Link", "Sources",
]
