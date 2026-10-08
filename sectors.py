"""Tag articles with the startup sectors they are about, based on the headline.

The social media / creator / influencer sectors come first and are the ones the
"Social & Creator" tab is built from; the broad sectors after them make the
Sector column useful for filtering the rest of the sheet too.
"""
import re

SOCIAL_SECTORS = [
    ("Influencer Marketing", r"influencers?|influencer[- ]marketing|kols?|key opinion leaders?|brand collaborations?|"
                             r"creator (?:marketing|partnerships?|campaigns?)|brand[- ]creator|"
                             r"affiliate marketing|celebrity endorsements?"),
    ("Creator Economy", r"creator economy|creators|content creators?|creator[- ](?:tech|platform|commerce|tools?|"
                        r"marketplace|network|fund|monetization|monetisation|led|first)|ugc|user[- ]generated|"
                        r"podcasters?|youtubers?|streamers?|newsletter platform|fan (?:engagement|economy|platform)"),
    ("Social Media Management", r"social media (?:management|marketing|scheduling|analytics|tools?|agency|agencies)|"
                                r"social listening|community management|smm"),
    ("Social Media", r"social media|social network(?:ing)?|social (?:app|platform|discovery|audio)|"
                     r"short[- ]video|short[- ]form video|live[- ]?stream(?:ing)?|memes?|dating app|"
                     r"community (?:app|platform)|instagram|youtube|tiktok|reels|snapchat|threads app|"
                     r"vernacular social|sharechat|moj|josh app"),
    ("Social Commerce", r"social[- ]commerce|live[- ]commerce|community commerce|creator commerce|reseller|"
                        r"video commerce|shoppable"),
]

OTHER_SECTORS = [
    ("Marketing / AdTech", r"martech|adtech|ad[- ]tech|advertising|marketing (?:platform|automation|agency|tech)|"
                           r"performance marketing|brand(?:ing)? agency"),
    ("AI", r"ai|artificial intelligence|genai|generative ai|llms?|agentic|machine learning|ml"),
    ("Fintech", r"fintech|payments?|lending|nbfc|neobank|insurtech|wealthtech|credit|banking"),
    ("SaaS / B2B", r"saas|b2b|enterprise software|devtools?|developer tools?|cybersecurity|security"),
    ("D2C / Consumer", r"d2c|dtc|consumer brand|beauty|skincare|fashion|apparel|food brand|beverage|"
                       r"personal care|jewellery|jewelry|home decor"),
    ("E-commerce / Quick Commerce", r"e-?commerce|quick[- ]commerce|marketplace|retail"),
    ("Healthtech", r"healthtech|health|healthcare|medtech|biotech|pharma|diagnostics|wellness|fitness"),
    ("Edtech", r"edtech|education|learning|upskilling|school"),
    ("Climate / Energy", r"climate|cleantech|clean energy|solar|ev charging|battery|carbon|sustainab\w*|renewable"),
    ("Mobility / EV", r"mobility|electric vehicles?|evs?|automotive|ride[- ]hailing"),
    ("Deeptech / Space / Robotics", r"deep[- ]?tech|space ?tech|spacetech|satellites?|robotics?|drones?|"
                                    r"semiconductors?|quantum|defen[cs]e[- ]?tech"),
    ("Gaming / Media / Entertainment", r"gaming|games?|esports|(?<!social )media|entertainment|ott|music|film|animation"),
    ("Agritech / Food", r"agri ?tech|agritech|agriculture|farm\w*|dairy|food ?tech"),
    ("Logistics / Supply Chain", r"logistics|supply chain|freight|warehousing|delivery"),
    ("Proptech / Real Estate", r"proptech|real estate|housing|construction|co-?working|co-?living"),
    ("Web3 / Crypto", r"web3|crypto\w*|blockchain|defi|nfts?|tokeni[sz]\w*"),
    ("HR / Future of Work", r"hr ?tech|hiring|recruitment|workforce|payroll|staffing"),
    ("Travel / Hospitality", r"travel|hospitality|hotels?|tourism"),
]

_COMPILED = [(name, re.compile(rf"\b(?:{pattern})\b", re.I)) for name, pattern in SOCIAL_SECTORS + OTHER_SECTORS]
SOCIAL_SECTOR_NAMES = {name for name, _ in SOCIAL_SECTORS}

# "GitHub Copilot's creator", "creator of X": a person, not the creator economy
_NOT_CREATOR_ECONOMY = re.compile(r"[’']s creator\b|\bcreator of\b|\bco-?creator\b", re.I)


def tag_sectors(text):
    """Return the matching sector names, social / creator sectors first."""
    tags = []
    for name, pattern in _COMPILED:
        match = pattern.search(text)
        if not match:
            continue
        if name == "Creator Economy" and _NOT_CREATOR_ECONOMY.search(text) and not re.search(
                r"creators|creator economy|content creator", text, re.I):
            continue
        tags.append(name)
    return tags


def is_social(sector_cell):
    return any(tag.strip() in SOCIAL_SECTOR_NAMES for tag in sector_cell.split(";"))
