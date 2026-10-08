"""Pull investor / fund / accelerator names out of funding headlines.

Headlines follow a handful of patterns ("X raises $5 Mn led by Y",
"Y leads Series A in X", "Y-backed X", "Y announces first close of Fund II"),
so simple patterns catch most names without needing an LLM.
"""
import re

# Words that end an investor-name phrase
_STOP = (
    r"(?:\s+(?:to|for|as|at|in|into|amid|with|via|on|after|ahead|while|that|who|which|"
    r"and others|among others|others|valuing|valuation|has|have|had|will|would|is|was|are|were|said|says|"
    r"also|himself|herself|themselves|this|through|under|over|since|during|among)\b"
    r"|\s+(?:and\s+)?(?:existing|other|new) investors(?=\s*(?:$|[.,;:]))"
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
    re.compile(r"^(?P<names>[^:;]+?)\s+(?:invests? in|co-invests?|backs?(?!\s+(?:to|from|on|in|up|down|off|out|away|into)\b)(?=\s+(?:[a-z][\w-]*\s+){0,4}[A-Z0-9])|bets on|doubles down on|picks up stake)\b"),
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
    "ceo", "cfo", "cto", "coo", "founder", "co-founder", "cofounder", "president", "chairman", "director",
    "crunchbase", "crunchbase news", "techcrunch", "inc42", "entrackr", "yourstory", "e27", "vccircle",
    "economic times", "et", "reuters", "bloomberg", "mint", "moneycontrol", "tracxn", "pitchbook",
    "vc", "vcs", "pe", "pe fund", "vc fund", "private equity", "venture", "ventures", "capital",
}


def _key(name):
    """Group spellings like 'Peak XV' / 'Peak XV Partners' or 'Accel' / 'Accel India'."""
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    stripped = re.sub(r"(?:partners|ventures|venture|capital|vc|advisors|investments|management|india)+$", "", key)
    return stripped or key

_LEADING_JUNK = re.compile(
    r"^(?:its|the|a|an|existing investor|existing investors|investor|investors|vc firm|vc|"
    r"venture capital firm|investment firm|fund|global|us-based|india-based|singapore-based|"
    r"early-stage vc|early stage vc|early-stage investor|clutch of|new investor|including|includes|like|such as|"
    r"marquee investors?|investors? like|angel investors?|angel investor)\s+", re.I
)
_AMOUNT = re.compile(r"(?:rs\.?|inr|usd|us\$|\$|₹|€|£)\s?[\d.,]+|\b[\d.,]+\s?(?:mn|million|cr|crore|bn|billion|lakh|k)\b", re.I)


def _clean(name):
    # Drop emoji / symbols around names ("Peak XV Partners 🎉", "Andreessen Horowitz—")
    name = re.sub(r"^[^\w(]+|[^\w).]+$", "", name.strip())
    name = re.sub(r"\.\s+(?:The|This|It|We|Our|Th)\b.*$", "", name)
    name = name.strip(" '\"‘’“”.,-–—")
    name = re.sub(r"^(?:and|&)\s+", "", name, flags=re.I)
    for _ in range(2):
        name = _LEADING_JUNK.sub("", name)
    name = re.sub(r"\s+(?:programme|program|accelerator program(?:me)?)$", "", name, flags=re.I)
    # "Startup-community platform D2C Insider" -> "D2C Insider"
    name = re.sub(r"^.*\b(?:platform|startup|firm|company|brand|maker|provider|investor)s?\s+(?=[A-Z0-9])", "", name)
    # Trailing lowercase words: "Bertelsmann India Investments will" -> "Bertelsmann India Investments"
    name = re.sub(r"(?:\s+[a-z][\w-]*)+$", "", name)
    if re.search(r"(?i)-based$", name) or re.match(r"(?i)(?:former|ex|current|then)\b", name):
        return None
    if re.match(r"(?i)(?:at|in|on|for|with|from|by|as|after|during|this|that|these|those|our|their|his|her)\b", name):
        return None
    name = re.sub(r"[’']s$", "", name).strip(" '\"‘’“”,-")
    name = re.sub(r"\b(\w+)\s+\1$", r"\1", name)  # "3one4 Capital Capital" -> "3one4 Capital"
    if "%" in name:
        return None
    if not name or _AMOUNT.search(name):
        return None
    # Must look like a proper name: a capitalised word (allows "pi Ventures", "3one4 Capital")
    if name.lower() in _NOT_NAMES or not re.search(r"(?:^|\s)[A-Z]", name):
        return None
    # Descriptive phrases ("defence technology startup X") have several lowercase words
    lowercase_words = [w for w in name.split() if w[0].islower() and w not in ("of", "the", "and", "de", "for", "in")]
    if len(lowercase_words) > 1:
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
                if name and name.lower() not in [f.lower() for f in found]:
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
                 r"a16z|andreessen|bessemer|tiger global|softbank|general catalyst|iron pillar|3one4|stellaris|chiratae|"
                 r"rainmatter|z47|ajvc|pi ventures|fireside|verlinvest|rebalance|oister|360 one|ipv|inflection point|norwest|piper serica|prosus|dsp|motilal|kotak|temasek|gic|ifc", lower):
        return "VC / PE Fund"
    return "Other (Corporate / Individual)"


def build_investor_table(rows):
    """rows: sheet rows [date, source, title, category, link, company, amount, round, investors].

    Uses the Investors column when present (it includes names found in the
    article text), otherwise falls back to the headline.
    """
    investors = {}
    for row in rows:
        if len(row) < 5 or not row[2]:
            continue
        date, source, title, _category, link = row[:5]
        if len(row) > 8 and row[8]:
            names = [_clean(n) for n in row[8].split(";") if n.strip() and n.strip() != "—"]
            names = [n for n in names if n]
        else:
            names = extract_investors(title)
        for name in names:
            entry = investors.setdefault(_key(name), {
                "name": name, "mentions": 0, "first": date, "latest": date,
                "title": title, "link": link, "sources": set(), "sectors": {}, "social": 0,
            })
            sectors = [t.strip() for t in (row[9] if len(row) > 9 else "").split(";") if t.strip()]
            for sector in sectors:
                entry["sectors"][sector] = entry["sectors"].get(sector, 0) + 1
            if any(t in SOCIAL_SECTOR_NAMES for t in sectors):
                entry["social"] += 1
            if len(name) > len(entry["name"]):
                entry["name"] = name  # show the fullest spelling, e.g. "Peak XV Partners"
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
            entry["social"],
            ", ".join(f"{name} ({count})" for name, count in
                      sorted(entry["sectors"].items(), key=lambda kv: -kv[1])[:6]),
        ])
    return table


from sectors import SOCIAL_SECTOR_NAMES  # noqa: E402  (sectors does not import this module)

INVESTOR_HEADER = [
    "Investor / Fund", "Type", "Mentions", "First Seen", "Latest Mention",
    "Latest Headline", "Latest Link", "Sources", "Social / Creator Deals", "Sectors (deals)",
]
