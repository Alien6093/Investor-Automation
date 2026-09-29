import urllib.request, re
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "application/rss+xml,application/xml,application/json,text/html;q=0.9,*/*;q=0.8"}
urls = [
 "https://entrackr.com/sitemap_2026-01-15.xml",
 "https://entrackr.com/news-sitemap.xml",
 "https://yourstory.com/sitemap_2026_week3.xml",
 "https://yourstory.com/news-sitemap.xml",
 "https://news.google.com/rss/search?q=site:businessworld.in+after:2026-01-01+before:2026-01-15&hl=en-IN&gl=IN&ceid=IN:en",
 "https://news.google.com/rss/search?q=site:businessworld.in+funding+when:30d&hl=en-IN&gl=IN&ceid=IN:en",
 "https://news.google.com/rss/search?q=site:f6s.com+accelerator&hl=en-IN&gl=IN&ceid=IN:en",
 "https://news.google.com/rss/search?q=site:tracxn.com&hl=en-IN&gl=IN&ceid=IN:en",
 "https://www.ycombinator.com/blog/rss/",
 "https://techcrunch.com/wp-json/wp/v2/posts?per_page=1&after=2026-01-01T00:00:00&categories=577030455",
 "https://news.crunchbase.com/wp-json/wp/v2/posts?per_page=1&after=2026-01-01T00:00:00",
 "https://www.medianama.com/wp-json/wp/v2/posts?per_page=1&after=2026-01-01T00:00:00",
 "https://e27.co/index_wp.php/wp-json/wp/v2/posts?per_page=1&after=2026-01-01T00:00:00",
 "https://e27.co/wp-json/wp/v2/posts?per_page=1&after=2026-01-01T00:00:00",
 "https://inc42.com/wp-json/wp/v2/posts?per_page=100&page=2&after=2026-01-01T00:00:00&_fields=date_gmt,link,title",
 "https://economictimes.indiatimes.com/tech/funding/rssfeeds/78570540.cms",
 "https://www.vccircle.com/",
 "https://www.businessworld.in/rss/business-news.xml",
]
for u in urls:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25)
        body = r.read(2000000).decode("utf-8", "ignore")
        hdr = {k: v for k, v in r.headers.items() if k.lower() in ("content-type", "x-wp-total", "x-wp-totalpages")}
        dates = re.findall(r'<(?:pubDate|lastmod|news:publication_date)>([^<]+)<', body)
        items = body.count("<item>") + body.count("<url>")
        print(f"OK {r.status} {r.geturl()} {hdr} len={len(body)} items={items} first_dates={dates[:2]} last_dates={dates[-2:]}")
        i = max(body.find("<item>"), body.find("<url>"), 0)
        print("   ", re.sub(r"\s+", " ", body[i:i+700]))
    except Exception as e:
        print(f"ERR {u} {e}")
