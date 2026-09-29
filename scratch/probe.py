import urllib.request, re
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "text/html;q=0.9,*/*;q=0.8"}


def fetch(u):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25)
    return r.read(4000000).decode("utf-8", "ignore")


legal = fetch("https://www.openvc.app/legal")
text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", "", legal)))
print("LEGAL length", len(text))
seen = set()
for m in re.finditer(r"(?i)(scrap|crawl|automat|robot|spider|harvest|reproduc|data mining|extract|bulk|systematic|resell|redistribut|intellectual property|database)", text):
    start = max(0, m.start() - 400)
    if any(abs(start - s) < 400 for s in seen):
        continue
    seen.add(start)
    print("   ...", text[start: m.end() + 400])

body = fetch("https://www.openvc.app/country/India?page=2")
i = body.find("fund/Piper%20Serica")
print("CARD HTML:")
print(body[max(0, i - 2500): i + 2500])
