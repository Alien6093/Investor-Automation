"""Turn a funding article into structured fields: company, amount, round, investors.

The headline is tried first. When it does not name the investors, the article's
summary / opening paragraphs are scanned sentence by sentence ("The round was led
by Accel, with participation from Blume Ventures ...").
"""
import re

from investor_extractor import extract_investors, _clean, _key, _SPLIT, _STOP

AMOUNT = re.compile(
    r"(?:(?:rs\.?|inr|usd|us\$|s\$|\$|₹|€|£)\s?\d[\d,]*(?:\.\d+)?\s?(?:mln|bln|mil|mn|million|cr|crore|bn|billion|lakh|k|m|b)?\b"
    r"|\b\d[\d,]*(?:\.\d+)?\s?(?:mln|bln|mn|million|cr|crore|bn|billion|lakh)\s?(?:usd|dollars|rupees|inr)?\b)",
    re.I,
)

ROUND = re.compile(
    r"\b(pre-seed|pre seed|seed|pre-series [a-f]|pre series [a-f]|series [a-h]\+?|bridge|angel|"
    r"growth|debt|venture debt|strategic|extended series [a-f])\b(?:\s+(?:round|funding|investment))?",
    re.I,
)

# Descriptors before the company name: "Deep-tech startup Aule Space", "D2C fashion brand MyDesignation"
_DESCRIPTOR = re.compile(
    r"^.*\b(?:startup|start-up|platform|brand|company|firm|maker|provider|marketplace|app|player|"
    r"unicorn|venture|operator|developer|manufacturer|lender|nbfc|fintech|edtech|healthtech|agritech|"
    r"saas|chain|studio|label|network|solution|solutions|service|services|builder|specialist|investor)s?,?\s+",
    re.I,
)

_RAISE_VERB = (r"(?:in talks to|looks to|set to|plans to|to) raise|raises|raised|secures|secured|bags|bagged|gets|nets|receives|pockets|lands|"
               r"closes|closed|mops up|garners|snags|scores|picks up|attracts|announces|completes")

# Extra patterns that only make sense in article body sentences
_BODY_PATTERNS = [
    re.compile(r"\b(?:joined by|investors? (?:include|including|such as|like)|along with)\s+(?P<names>.+?)" + _STOP, re.I),
    re.compile(r"^(?P<names>[^,]+?)\s+(?:co-)?led the (?:round|funding|investment|financing)", re.I),
    re.compile(r"^(?:existing\s+|new\s+)?(?:investors?\s+)?(?P<names>[^,]{2,60}?(?:,[^,]{2,60}?)*)\s+(?:also\s+)?(?:participated|joined)\b", re.I),
    re.compile(r"\b(?:saw|with|had|also saw) (?:the )?participation (?:from|of)\s+(?P<names>.+?)" + _STOP, re.I),
]


def extract_company(title):
    patterns = [
        r"^[^,]+?(?:,[^,]+?)*\s+(?:back|backs|invest in|invests in)\s+(?P<co>.+?)\s+(?:in|with)\b",
        rf"^(?P<co>.+?)\s+(?:{_RAISE_VERB})\b",
        r"\b(?:leads?|co-leads?|invests?|backs?)\b.*?\b(?:in|into)\s+(?P<co>.+?)(?:\s+(?:to|for|as|amid|at)\b|[,:;]|$)",
        r"^[^,]+?\s+(?:invests in|backs)\s+(?P<co>.+?)(?:\s+(?:to|for|as|amid|at)\b|[,:;]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, title, re.I)
        if not match:
            continue
        company = match.group("co").strip(" '\"‘’“”")
        company = re.sub(r"^[^\w]+", "", company)                      # leading emoji / symbols
        company = company.rsplit(": ", 1)[-1]                           # "BREAKING: X", "Forget the feed: X"
        company = re.sub(r"^.*-backed\s+", "", company, flags=re.I)     # "Prime Focus-backed Brahma AI"
        company = re.sub(r"^[\w.-]+-based\s+", "", company, flags=re.I)  # "Paris-based Rayon"
        company = re.sub(r"^[A-Z][a-z]+[’']s\s+(?=[A-Z0-9])", "", company)  # "Germany’s Reverion"
        company = re.sub(r"(?:\s+(?:has|have|just|officially|finally|also|today|now))+$", "", company, flags=re.I)
        company = _DESCRIPTOR.sub("", company)
        if re.match(r"(?i)(?:we|i|our|my|they|he|she|it|this|just|big|excited|exciting|thrilled|proud|so|"
                    r"why|how|what|when|where|who|should|can|could|is|are|will|would|does|do|here)\b", company):
            continue
        company = re.sub(r"[’']s$", "", company).strip(" ,-'\"‘’“”")
        # A bare description ("short-video app") is not a company name
        if re.fullmatch(r"[a-z0-9 -]+\s(?:app|platform|startup|company|brand|firm|player)s?", company):
            continue
        if (company and len(company.split()) <= 6 and re.search(r"[A-Za-z]", company)
                and not AMOUNT.search(company)):
            return company
    return ""


def _investors_from_text(text):
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"])", text):
        found += [n for n in extract_investors(sentence) if n not in found]
        for pattern in _BODY_PATTERNS:
            for match in pattern.finditer(sentence):
                for part in _SPLIT.split(match.group("names")):
                    name = _clean(part)
                    if name and name not in found:
                        found.append(name)
    return found


ROUNDUP = re.compile(r"\b(this week|weekly|roundup|round-up|biggest (?:funding )?rounds|funding rundown|top \d+|"
                     r"week's|weeks|others raise|and more)\b", re.I)


def is_single_deal(title):
    """A headline about one company's round (not a roundup / essay / market story)."""
    return bool(extract_company(title)) and not ROUNDUP.search(title)


def extract_deal(title, text=""):
    """Return dict(company, amount, round, investors[list]) for an article."""
    if ROUNDUP.search(title):
        return {"company": "", "amount": "", "round": "", "investors": []}
    investors = extract_investors(title)
    company = extract_company(title)
    if not company and not investors:
        return {"company": "", "amount": "", "round": "", "investors": []}
    # For fund launches the article names LPs / portfolio companies, not investors in a startup
    fund_launch = re.search(r"\bfunds?\b|\bcorpus\b", title, re.I)
    if not investors and text and company and not fund_launch:
        investors = _investors_from_text(text)
    # Keep one spelling per investor ("Bertelsmann India" / "Bertelsmann India Investments")
    unique = {}
    for name in investors:
        key = _key(name)
        if key not in unique or len(name) > len(unique[key]):
            unique[key] = name
    investors = list(unique.values())
    # The startup itself is sometimes caught as a name ("X raises from Y" in body text)
    if company:
        investors = [n for n in investors if n.lower() != company.lower()]
    amount = AMOUNT.search(title) or (AMOUNT.search(text[:600]) if text else None)
    round_ = ROUND.search(title) or (ROUND.search(text[:600]) if text else None)
    return {
        "company": company,
        "amount": amount.group(0).strip() if amount else "",
        "round": round_.group(1).title().replace("Pre Seed", "Pre-Seed") if round_ else "",
        "investors": investors[:12],
    }
