import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML as cur

r = subprocess.run(
    ["git", "show", "HEAD:agents/linkedin_perfil_page.py"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    cwd=ROOT,
)
text = r.stdout
start = text.find("LINKEDIN_PERFIL_PAGE_HTML: str = ")
chunk = text[start + 30 :]
q = chunk[0]
# multiline string in repr
old_h = ast.literal_eval(chunk.split("\n\nfrom __future__")[0].rstrip() if "\n\nfrom" in chunk else chunk.rsplit("'", 1)[0] + "'")
# simpler: read file from git and exec
exec_globals = {}
exec(text, exec_globals)
old_h = exec_globals.get("LINKEDIN_PERFIL_PAGE_HTML", "")


def extract_overview(h: str) -> str:
    if "panel-overview" not in h:
        return ""
    part = h.split('id="panel-overview"', 1)[1]
    if 'id="panel-posts"' in part:
        return part.split('id="panel-posts"', 1)[0]
    if 'id="panel-content"' in part:
        return part.split('id="panel-content"', 1)[0]
    return part[:12000]


def report(h: str, name: str) -> None:
    ov = extract_overview(h)
    print(f"=== {name} len={len(ov)} ===")
    keys = [
        "Principais Insights",
        "Indicadores de desempenho",
        "li-profile-overview",
        "li-profile-hero",
        "problemas_identificados",
        "renderLinkedinHarvestOverview",
        "metricas_universais",
    ]
    for kw in keys:
        print(f"  {kw}: {kw in ov}")


report(cur, "CURRENT")
report(old_h, "GIT_HEAD")

cur_ov = extract_overview(cur)
git_ov = extract_overview(old_h)
if cur_ov != git_ov:
    out = ROOT / "scripts" / "_overview_cur.txt"
    out2 = ROOT / "scripts" / "_overview_git.txt"
    out.write_text(cur_ov[:15000], encoding="utf-8")
    out2.write_text(git_ov[:15000], encoding="utf-8")
    print("DIFF written to scripts/_overview_*.txt")
else:
    print("Overview identical to git HEAD")
