import os
import json
import re
from datetime import datetime
import feedparser
import gspread
from google.oauth2.service_account import Credentials

# Fetch articles published on or after Jan 1, 2026
CUTOFF_DATE = datetime(2026, 1, 1)

# Targeted RSS Feeds
FEEDS = {
    "Entrackr": "https://entrackr.com/feed/",
    "Inc42": "https://inc42.com/feed/",
    "YourStory": "https://yourstory.com/feed",
    "BW Businessworld": "https://www.businessworld.in/rss/business-news.xml",
    "Y Combinator Blog": "https://blog.ycombinator.com/rss/"
}

# Regex filters for Funding, Corporate VCs, Accelerators, and Investment news
KEYWORDS = re.compile(
    r'\b(funding|funded|raises|raised|pre-seed|seed round|series a|series b|series c|'
    r'venture capital|corporate vc|accelerator|incubator|cohort|demo day|'
    r'backed by|flipkart ventures|y combinator|investor|lead investor|valuation)\b',
    re.IGNORECASE
)

def categorize_article(text):
    text_lower = text.lower()
    if any(term in text_lower for term in ["accelerator", "cohort", "demo day", "incubator"]):
        return "Accelerator Program"
    elif any(term in text_lower for term in ["pre-seed", "seed", "series a", "series b", "raises", "raised"]):
        return "Startup Funding"
    elif any(term in text_lower for term in ["venture capital", "vc", "fund", "flipkart ventures"]):
        return "VC / Fund News"
    return "General Investment"

def setup_google_sheet():
    creds_json = json.loads(os.environ["GCP_SERVICE_ACCOUNT_KEY"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("VC & Funding Tracker").sheet1

def run():
    sheet = setup_google_sheet()
    
    # Get existing URLs to avoid duplicate rows
    existing_urls = set(sheet.col_values(5)[1:]) if sheet.row_count > 1 else set()
    new_rows = []

    for source_name, feed_url in FEEDS.items():
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            pub_tuple = entry.get("published_parsed") or entry.get("updated_parsed")
            if not pub_tuple:
                continue
            
            pub_date = datetime(*pub_tuple[:6])
            if pub_date < CUTOFF_DATE:
                continue

            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")

            # Apply VC/Funding Filter
            if KEYWORDS.search(title) or KEYWORDS.search(summary):
                if link not in existing_urls:
                    category = categorize_article(title + " " + summary)
                    date_str = pub_date.strftime("%Y-%m-%d %H:%M")
                    new_rows.append([date_str, source_name, title, category, link])
                    existing_urls.add(link)

    if new_rows:
        sheet.append_rows(new_rows)
        print(f"Successfully added {len(new_rows)} relevant funding/VC items.")
    else:
        print("No new funding or accelerator updates found.")

if __name__ == "__main__":
    run()
