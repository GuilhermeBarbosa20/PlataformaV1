# -*- coding: utf-8 -*-
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

replacements = [
    (
        "linkedin\\.com\\/company\\/([a-zA-Z0-9\\-_%]+)/i",
        "linkedin\\.com\\/company\\/([a-zA-Z0-9\\-_%]+)/i",
    ),
]
# Add school to canonicalize - after company match block
old = """                m = noHash.match(/linkedin\\.com\\/company\\/([a-zA-Z0-9\\-_%]+)/i);
                if (m && m[1]) return "https://www.linkedin.com/company/" + decodeURIComponent(m[1]).replace(/\\/$/, "");
                if (!/^https?:\\/\\//i.test(noHash)"""
new = """                m = noHash.match(/linkedin\\.com\\/company\\/([a-zA-Z0-9\\-_%]+)/i);
                if (m && m[1]) return "https://www.linkedin.com/company/" + decodeURIComponent(m[1]).replace(/\\/$/, "");
                m = noHash.match(/linkedin\\.com\\/school\\/([a-zA-Z0-9\\-_%]+)/i);
                if (m && m[1]) return "https://www.linkedin.com/school/" + decodeURIComponent(m[1]).replace(/\\/$/, "");
                if (!/^https?:\\/\\//i.test(noHash)"""
if old in h:
    h = h.replace(old, new, 1)

h = h.replace(
    "/linkedin\\.com\\/(in|company)\\//i.test(noHash)",
    "/linkedin\\.com\\/(in|company|school)\\//i.test(noHash)",
)

h = h.replace(
    "linkedin.com/(in|company)/",
    "linkedin.com/(in|company|school)/",
)

h = h.replace(
    "https://www.linkedin.com/in/nome ou /company/empresa",
    "https://www.linkedin.com/in/nome, /company/empresa ou /school/escola",
)

h = h.replace(
    "ex.: https://www.linkedin.com/in/nome).",
    "ex.: https://www.linkedin.com/in/nome ou /school/escola).",
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("school in page", "/school/" in h and "linkedin.com/school" in h)
