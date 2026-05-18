from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app.py"
t = p.read_text(encoding="utf-8")
marker_start = "def _linkedin_cookie_secure()"
marker_end = '@app.post("/agents/linkedin/resolve-profile-url")'
if marker_start not in t:
    raise SystemExit("start marker not found")
if marker_end not in t:
    raise SystemExit("end marker not found")
s = t.index(marker_start)
e = t.index(marker_end)
p.write_text(t[:s] + t[e:], encoding="utf-8")
print("removed", e - s, "chars")
