import urllib.request, re, json
from urllib.parse import quote_plus
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "application/rss+xml,application/xml,application/json,text/html;q=0.9,*/*;q=0.8"}

def gn(q):
    return f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-IN&gl=IN&ceid=IN:en"

urls = [
 ("yc-batches", "https://yc-oss.github.io/api/batches/index.json"),
 ("yc-w26", "https://yc-oss.github.io/api/batches/winter-2026.json"),
 ("yc-s26", "https://yc-oss.github.io/api/batches/summer-2026.json"),
 ("yc-x26", "https://yc-oss.github.io/api/batches/spring-2026.json"),
 ("indianstartupnews rss", "https://indianstartupnews.com/rss"),
 ("indianstartupnews feed", "https://indianstartupnews.com/feed/"),
 ("startupstorymedia", "https://startupstorymedia.com/feed/"),
 ("thebridge/entrepreneur india", "https://www.entrepreneur.com/en-in/rss"),
 ("moneycontrol startup rss", "https://www.moneycontrol.com/rss/startup.xml"),
 ("livemint companies/start-ups", "https://www.livemint.com/rss/companies"),
 ("business standard startups", "https://www.business-standard.com/rss/companies/start-ups-10116.rss"),
 ("fortune india startups", "https://www.fortuneindia.com/rss/startups"),
 ("startuptalky wp", "https://startuptalky.com/wp-json/wp/v2/posts?per_page=1"),
 ("techstars blog", "https://www.techstars.com/blog/rss.xml"),
 ("500 global", "https://500.co/blog/rss.xml"),
 ("startup india", "https://www.startupindia.gov.in/"),
 ("GN accelerator cohort", gn('(accelerator OR incubator) (cohort OR "applications open" OR "demo day" OR selects) startups after:2026-06-01 before:2026-06-08')),
 ("GN fund close", gn('("first close" OR "final close" OR "launches fund" OR "maiden fund" OR "new fund") (venture OR VC) after:2026-06-01 before:2026-06-08')),
 ("GN funding led by", gn('startup raises "led by" after:2026-06-01 before:2026-06-08')),
 ("GN dealstreetasia", gn('site:dealstreetasia.com after:2026-06-01 before:2026-06-08')),
 ("GN business-standard startups", gn('site:business-standard.com startup funding after:2026-06-01 before:2026-06-08')),
 ("GN moneycontrol startup", gn('site:moneycontrol.com startup funding after:2026-06-01 before:2026-06-08')),
 ("GN linkedin posts", gn('site:linkedin.com funding "led by" after:2026-06-01 before:2026-06-08')),
]
for name, u in urls:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25)
        body = r.read(3000000).decode("utf-8", "ignore")
        items = body.count("<item>") + body.count("<entry>")
        titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", body)[1:5]
        extra = ""
        if body.lstrip().startswith(("[", "{")):
            data = json.loads(body)
            extra = f"json len={len(data)} sample={json.dumps(data[:2] if isinstance(data, list) else list(data)[:10])[:600]}"
        print(f"OK {r.status} {name} {r.headers.get('content-type')} items={items} titles={titles} {extra}")
    except Exception as e:
        print(f"ERR {name} {u[:90]} {e}")
