"""Read-only: count social media / creator / influencer rows in Sheet1."""
import re, collections, sys
sys.path.insert(0, ".")
import fetch_vc_news as f

SOCIAL = re.compile(
    r"\b(social media|social[- ]commerce|social network|social app|influencer|creator economy|creators?\b|"
    r"content creator|ugc|user[- ]generated|short[- ]video|community platform|smm|social listening|"
    r"social media management|creator[- ]tech|live[- ]stream|livestream|meme|instagram|youtube|tiktok|"
    r"reels|brand collaborations?|affiliate marketing|kol)\b", re.I)

sheet = f.setup_google_sheet()
rows = sheet.get_all_values()
header, rows = rows[0], rows[1:]
print("Header:", header, "rows:", len(rows))
hits = [r for r in rows if SOCIAL.search(r[2])]
print("Rows whose headline mentions social / creator / influencer terms:", len(hits))
print("  ...of which single deals (Company filled):", sum(1 for r in hits if len(r) > 5 and r[5]))
print("  ...of which name investors:", sum(1 for r in hits if len(r) > 8 and r[8] not in ("", "—")))
terms = collections.Counter(m.group(0).lower() for r in hits for m in SOCIAL.finditer(r[2]))
print("Term counts:", terms.most_common(25))
srcs = collections.Counter(r[1] for r in hits)
print("By source:", srcs.most_common(20))
months = collections.Counter(r[0][:7] for r in hits)
print("By month:", sorted(months.items()))
print("SAMPLE:")
for r in hits[:: max(1, len(hits) // 60)]:
    print("   ", r[0][:10], "|", r[1][:18], "|", r[2][:95], "|", (r[8] if len(r) > 8 else "")[:60])
