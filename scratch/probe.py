import urllib.request, re
from urllib.parse import quote_plus
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "application/rss+xml,application/xml,text/html;q=0.9,*/*;q=0.8"}
def gn(q): return f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-IN&gl=IN&ceid=IN:en"
urls = [
 "https://www.netinfluencer.com/feed/", "https://www.tubefilter.com/feed/", "https://digiday.com/feed/",
 "https://www.socialmediatoday.com/feeds/news/", "https://www.afaqs.com/rss", "https://www.exchange4media.com/rss",
 "https://www.storyboard18.com/rss", "https://influencermarketinghub.com/feed/", "https://www.thepublishpress.com/feed",
 "https://www.passionfru.it/feed", "https://www.creatoreconomy.so/feed", "https://www.businessofinfluencers.com/feed",
 "https://www.adweek.com/feed/", "https://www.marketing-interactive.com/rss", "https://www.campaignasia.com/rss/rss.ashx",
 "https://www.medianews4u.com/feed/", "https://bestmediainfo.com/feed",
 gn('("influencer marketing" OR "creator economy" OR "social media" OR "social commerce" OR "creator platform") (raises OR funding OR "seed round" OR "series a" OR invests OR backs) after:2026-06-01 before:2026-06-15'),
 gn('("creator economy" OR "influencer marketing" OR "social commerce") (VC OR "venture capital" OR "why we invested" OR investors) after:2026-06-01 before:2026-06-15'),
 gn('site:linkedin.com ("influencer marketing" OR "creator economy" OR "social media") (raised OR "funding round" OR "led by") after:2026-06-01 before:2026-06-15'),
]
for u in urls:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25)
        body = r.read(2000000).decode("utf-8", "ignore")
        items = body.count("<item") + body.count("<entry")
        dates = re.findall(r"<(?:pubDate|updated|published)>([^<]+)<", body)
        titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", body)[1:6]
        wp = "wp-content" in body
        print(f"OK {r.status} items={items} wp={wp} newest={dates[0] if dates else None} {u[:110]}\n     {titles}")
    except Exception as e:
        print(f"ERR {u[:110]} {e}")
