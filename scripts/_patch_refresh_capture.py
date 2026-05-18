import json
from pathlib import Path
PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
old = "                  if (data.session) {\n                    const u = data.session.user;"
new = "                  if (data.session) {\n                    captureLinkedinOAuthTokens(data.session);\n                    const u = data.session.user;"
if old in h and "captureLinkedinOAuthTokens(data.session)" not in h.split("refreshLinkedinSupabaseSession")[1][:800]:
    h = h.replace(old, new, 1)
PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
