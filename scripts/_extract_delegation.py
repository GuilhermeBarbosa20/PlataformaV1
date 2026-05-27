import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)
i = h.find("const linkedinMetricDetailStore")
Path("scripts/_delegation_snip.txt").write_text(h[i : i + 3500], encoding="utf-8")
