"""Build the Deals and Accelerators tabs from the article rows.

Article rows: [date, source, title, category, link, company, amount, round, investors]
"""
import re

from investor_extractor import investor_type, _clean, _key

NOT_FOUND = "—"

DEALS_HEADER = ["Date", "Company", "Amount", "Round", "Investors", "Headline", "Source", "Link"]

ACCELERATOR_HEADER = [
    "Program", "Mentions", "First Seen", "Latest Mention", "Latest Headline", "Latest Link",
    "Companies Mentioned", "Sources",
]

# "Peak XV's Surge", "Google for Startups Accelerator", "NASSCOM 10000 Startups", "Antler India"
_PROGRAM_PATTERNS = [
    re.compile(r"((?:[A-Z0-9][\w&.'’-]*\s+){0,4}[A-Z0-9][\w&.'’-]*)\s+(?:accelerator|incubator|launchpad|fellowship)\b"),
    re.compile(r"[’']s\s+((?:[A-Z][\w-]*\s+){0,2}[A-Z][\w-]*)\s+(?:accelerator|incubator|programme|program|cohort)\b"),
    re.compile(r"^((?:[A-Z0-9][\w&.'’-]*\s+){0,4}[A-Z0-9][\w&.'’-]*)\s+(?:selects|picks|unveils|announces|opens applications|launches)\b.*\b(?:cohort|batch|accelerator|programme|program)\b"),
    re.compile(r"\b(Y Combinator|YC|Techstars|500 Global|Antler|Surge|Sequoia Spark|Google for Startups|"
               r"Microsoft for Startups|AWS Activate|NVIDIA Inception|Plug and Play|Startupbootcamp|"
               r"Venture Catalysts|T-Hub|CIIE\.CO|NSRCEL|Villgro|Axilor|Zone Startups|Startup India)\b"),
]

_GENERIC = {
    "the", "a", "an", "new", "global", "startup", "startups", "its", "india", "indian", "first", "second",
    "third", "this", "ai", "deeptech", "fintech", "edtech", "healthtech", "climate", "women", "program",
    "programme", "accelerator", "incubator", "cohort", "e-commerce", "ecommerce", "d2c", "saas", "b2b",
    "tech", "deep-tech", "deeptech", "climate-tech", "sector", "industry",
}


def _program_names(title):
    names = []
    for pattern in _PROGRAM_PATTERNS:
        for match in pattern.finditer(title):
            name = _clean(match.group(1).strip())
            if name == "YC":
                name = "Y Combinator"
            if not name or name.lower() in _GENERIC:
                continue
            if _key(name) not in [_key(n) for n in names]:
                names.append(name)
    return names


def dedupe_deals(rows, days=45):
    """Drop repeat coverage of the same round (same company within `days`), keeping the
    report that names the most investors. Rows that aren't single deals pass through."""
    from datetime import datetime, timedelta
    kept, seen = [], {}
    for row in sorted(rows, key=lambda r: (r[0], -(len(r[8].split(";")) if len(r) > 8 and r[8] != NOT_FOUND else 0))):
        company = row[5] if len(row) > 5 else ""
        if not company:
            kept.append(row)
            continue
        key = _key(company)
        date = datetime.strptime(row[0][:10], "%Y-%m-%d")
        prev = seen.get(key)
        if prev is not None and date - prev[0] <= timedelta(days=days):
            best = prev[1]
            # Keep the version that names more investors
            if row[8] != NOT_FOUND and (best[8] == NOT_FOUND or len(row[8].split(";")) > len(best[8].split(";"))):
                kept[kept.index(best)] = row
                seen[key] = (prev[0], row)
            continue
        seen[key] = (date, row)
        kept.append(row)
    return kept


def build_deals_table(rows):
    """One row per single-company deal that names its investors, newest first."""
    deals = [row for row in dedupe_deals(rows) if len(row) >= 9 and row[5] and row[8] and row[8] != NOT_FOUND]
    deals.sort(key=lambda row: row[0], reverse=True)
    return [[row[0], row[5], row[6], row[7], row[8], row[2], row[1], row[4]] for row in deals]


def build_accelerator_table(rows):
    """Accelerator / incubator programs seen in the news, with the companies they back."""
    programs = {}
    for row in rows:
        if len(row) < 5 or not row[2]:
            continue
        date, source, title, category, link = row[:5]
        company = row[5] if len(row) > 5 else ""
        investors = [n.strip() for n in (row[8] if len(row) > 8 else "").split(";") if n.strip() and n.strip() != NOT_FOUND]
        names = []
        if category == "Accelerator Program":
            # Skip the company itself ("E-commerce accelerator Assiduus Global raises ...")
            names += [n for n in _program_names(title) if not company or n.lower() != company.lower()]
        names += [n for n in investors if investor_type(n) == "Accelerator / Incubator"]
        for name in names:
            entry = programs.setdefault(_key(name), {
                "name": name, "mentions": 0, "first": date, "latest": date,
                "title": title, "link": link, "companies": [], "sources": set(),
            })
            if len(name) > len(entry["name"]):
                entry["name"] = name
            entry["mentions"] += 1
            entry["sources"].add(source)
            if company and company not in entry["companies"]:
                entry["companies"].append(company)
            if date < entry["first"]:
                entry["first"] = date
            if date >= entry["latest"]:
                entry["latest"], entry["title"], entry["link"] = date, title, link

    table = []
    for entry in sorted(programs.values(), key=lambda e: (-e["mentions"], e["name"].lower())):
        table.append([
            entry["name"], entry["mentions"], entry["first"], entry["latest"], entry["title"], entry["link"],
            "; ".join(entry["companies"][:30]), ", ".join(sorted(entry["sources"])),
        ])
    return table
