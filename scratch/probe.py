import urllib.request, re, json
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "text/html,application/rss+xml,application/xml,application/json;q=0.9,*/*;q=0.8"}


def fetch(u, n=3000000):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25)
    return r.status, r.headers.get("content-type"), r.read(n).decode("utf-8", "ignore")


print("=== OpenVC ===")
for u in ["https://www.openvc.app/robots.txt"]:
    try:
        st, ct, body = fetch(u)
        print(u, st, "\n", body[:3000])
    except Exception as e:
        print("ERR", u, e)
for u in ["https://www.openvc.app/terms", "https://www.openvc.app/terms-of-service", "https://www.openvc.app/tos"]:
    try:
        st, ct, body = fetch(u)
        text = re.sub(r"<[^>]+>", " ", body)
        text = re.sub(r"\s+", " ", text)
        print(u, st, len(text))
        for m in re.finditer(r"(?i)(scrap|crawl|automat|robot|harvest|copy|reproduc|commercial use|data mining|extract)", text):
            print("   ...", text[max(0, m.start() - 250): m.end() + 250])
    except Exception as e:
        print("ERR", u, e)
for u in ["https://www.openvc.app/country/India", "https://www.openvc.app/country/India?page=2"]:
    try:
        st, ct, body = fetch(u)
        nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
        links = sorted(set(re.findall(r'href="(/fund/[^"]+|/investor/[^"]+|/vc/[^"]+)"', body)))
        print(u, st, ct, "len", len(body), "next_data", bool(nd), "links", len(links), links[:8])
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", re.sub(r"(?is)<(script|style).*?</\1>", "", body)))
        print("   TEXT:", text[:2500])
        if nd:
            print("   NEXT_DATA keys:", nd.group(1)[:1500])
    except Exception as e:
        print("ERR", u, e)

print("=== feeds ===")
feeds = [
 "https://www.finsmes.com/feed", "https://techfundingnews.com/feed/", "https://www.eu-startups.com/feed/",
 "https://sifted.eu/feed", "https://venturebeat.com/feed/", "https://techcrunch.com/category/startups/feed/",
 "https://kr-asia.com/feed", "https://www.techinasia.com/feed", "https://disrupt-africa.com/feed/",
 "https://www.wamda.com/feed", "https://www.startupdaily.net/feed/", "https://www.vcnewsdaily.com/rss",
 "https://www.financialexpress.com/business/start-ups/feed/", "https://www.businesstoday.in/rss/startups",
 "https://techstory.in/feed/", "https://startupreporter.in/feed/", "https://www.thehindubusinessline.com/companies/feeder/default.rss",
 "https://economictimes.indiatimes.com/small-biz/startups/rssfeeds/11993050.cms",
 "https://a16z.com/feed/", "https://avc.com/feed/", "https://www.saastr.com/feed/", "https://www.nfx.com/feed",
 "https://blog.google/outreach-initiatives/entrepreneurs/rss/", "https://www.antler.co/blog/rss.xml",
 "https://www.thesaasnews.com/feed", "https://www.alleywatch.com/feed/", "https://www.geekwire.com/fundings/feed/",
 "https://www.pehub.com/feed/", "https://www.privateequitywire.co.uk/feed", "https://ventureburn.com/feed/",
 "https://www.startupindia.gov.in/content/sih/en/rss.xml", "https://www.indianretailer.com/rss/startups.xml",
 "https://www.thestartupsquad.com/feed/", "https://www.startupnewsasia.com/feed/",
]
for u in feeds:
    try:
        st, ct, body = fetch(u, 800000)
        items = body.count("<item") + body.count("<entry")
        dates = re.findall(r"<(?:pubDate|updated|published)>([^<]+)<", body)
        titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", body)[1:4]
        wp = "wp-content" in body or "wordpress" in body.lower()
        print(f"OK {st} items={items} wp={wp} last={dates[-1] if dates else None} {u} {titles}")
    except Exception as e:
        print(f"ERR {u} {e}")
