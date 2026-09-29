import urllib.request, re
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "application/rss+xml,application/xml,application/json,text/html;q=0.9,*/*;q=0.8"}
urls = [
 "https://entrackr.com/rss", "https://entrackr.com/feed", "https://entrackr.com/rss.xml",
 "https://entrackr.com/wp-json/wp/v2/posts?per_page=1", "https://entrackr.com/sitemap.xml", "https://entrackr.com/robots.txt",
 "https://entrackr.com/",
 "https://inc42.com/wp-json/wp/v2/posts?per_page=1&after=2026-01-01T00:00:00", "https://inc42.com/feed/?paged=5",
 "https://yourstory.com/wp-json/wp/v2/posts?per_page=1", "https://yourstory.com/sitemap.xml", "https://yourstory.com/robots.txt",
 "https://www.businessworld.in/rss/business-news.xml", "https://www.businessworld.in/robots.txt", "https://www.businessworld.in/",
 "https://www.businessworld.in/sitemap.xml", "https://bwdisrupt.businessworld.in/", "https://www.businessworld.in/rss",
 "https://www.ycombinator.com/blog/rss/",
 "https://www.f6s.com/programs", "https://www.f6s.com/rss", "https://tracxn.com/",
 "https://www.vccircle.com/rss", "https://economictimes.indiatimes.com/tech/funding/rssfeeds/78570540.cms",
 "https://economictimes.indiatimes.com/tech/startups/rssfeeds/78570550.cms",
 "https://techcrunch.com/category/venture/feed/", "https://news.crunchbase.com/feed/",
 "https://www.livemint.com/rss/companies", "https://startupnews.fyi/feed/", "https://www.medianama.com/feed/",
 "https://e27.co/feed/", "https://indianstartupnews.com/feed", "https://www.thehindubusinessline.com/info-tech/feeder/default.rss",
]
for u in urls:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20)
        body = r.read(300000).decode("utf-8", "ignore")
        hdr = {k: v for k, v in r.headers.items() if k.lower() in ("content-type", "x-wp-total", "x-wp-totalpages")}
        feeds = set(re.findall(r'<link[^>]+type="application/(?:rss|atom)\+xml"[^>]*href="([^"]+)"', body))
        sm = re.findall(r'(?i)sitemap:\s*(\S+)', body)
        locs = re.findall(r'<loc>([^<]+)</loc>', body)
        print(f"OK {r.status} {r.geturl()} {hdr} len={len(body)} feeds={list(feeds)[:5]} sitemaps={sm[:8]} locs={locs[:6]}")
        print("   ", re.sub(r"\s+", " ", body[:250]))
    except Exception as e:
        print(f"ERR {u} {e}")
