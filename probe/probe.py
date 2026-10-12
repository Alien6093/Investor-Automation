import requests, re, json
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
     "Accept-Language": "en-IN,en;q=0.9"}
URLS = [
    "https://lu.ma/bengaluru", "https://lu.ma/mumbai", "https://api.lu.ma/discover/get-paginated-events?discover_place_api_id=discplace-G0tGUVYwl7T17Sb&pagination_limit=5",
    "https://www.eventbrite.com/d/india/investor/", "https://www.eventbrite.com/d/india--bangalore/startup-pitch/",
    "https://www.meetup.com/find/?keywords=startup%20investors&location=in--Bangalore&source=EVENTS",
    "https://allevents.in/bangalore/startup", "https://www.district.in/events/",
    "https://manage-api.konfhub.com/featured-events", "https://json.commudle.com/api/v2/events/public?when=future&limit=5",
    "https://www.headstart.in/_levo/cdn/api/v1/event/event/query?query=%7B%22limit%22%3A2%7D",
    "https://www.townscript.com/in/india/startup", "https://10times.com/india/startup", "https://tie.org/events/",
    "https://hasgeek.com/", "https://news.google.com/rss/search?q=investor+meet+India&hl=en-IN&gl=IN&ceid=IN:en",
]
for u in URLS:
    try:
        r = requests.get(u, headers=H, timeout=30)
        n = len(re.findall(r'"@type"\s*:\s*"Event"', r.text))
        print(f"PROBE {r.status_code} size={len(r.text)} events_ld={n} {u}")
    except Exception as e:
        print(f"PROBE ERR {e.__class__.__name__} {u}")
