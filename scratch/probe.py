import urllib.request, re, json
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"}


def fetch(u, n=4000000):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25)
    return r.read(n).decode("utf-8", "ignore")


body = fetch("https://www.openvc.app/country/India?page=2")
hrefs = sorted(set(re.findall(r'href="([^"]+)"', body)))
print("ALL HREFS (", len(hrefs), "):")
for h in hrefs:
    print("  ", h)
# Terms / legal links
for h in hrefs:
    if re.search(r"(?i)term|legal|privacy|policy|cgu|conditions", h):
        u = h if h.startswith("http") else "https://www.openvc.app" + h
        try:
            t = fetch(u)
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", "", t)))
            print("LEGAL", u, len(text))
            for m in re.finditer(r"(?i)(scrap|crawl|automat|robot|spider|harvest|reproduc|data mining|extract|bulk|systematic|resell|redistribut)", text):
                print("   ...", text[max(0, m.start() - 300): m.end() + 300])
        except Exception as e:
            print("ERR", u, e)
# Where does the investor list start? print a raw HTML window after the H1
i = body.find("Top Venture Capital Firms")
j = body.find("</h1>")
print("RAW HTML WINDOW:")
print(body[j:j + 6000])
print("PAGINATION:", sorted(set(re.findall(r"page=(\d+)", body)))[-5:])
try:
    sm = fetch("https://www.openvc.app/sitemap.xml", 400000)
    print("SITEMAP:", re.findall(r"<loc>([^<]+)</loc>", sm)[:40])
except Exception as e:
    print("ERR sitemap", e)
