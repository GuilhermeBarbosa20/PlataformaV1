import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML as cur

raw = subprocess.run(
    ["git", "show", "HEAD:agents/linkedin_perfil_page.py"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    cwd=ROOT,
).stdout

# HEAD uses json.dumps
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
git_h = json.loads(rest.strip())


def ov(h):
    return h.split('id="panel-overview"', 1)[1].split('id="panel-posts"', 1)[0]


cur_ov = ov(cur)
git_ov = ov(git_h)
print("cur len", len(cur_ov), "git len", len(git_ov))
print("equal", cur_ov == git_ov)
if cur_ov != git_ov:
    Path(ROOT / "scripts/_ov_cur.txt").write_text(cur_ov, encoding="utf-8")
    Path(ROOT / "scripts/_ov_git.txt").write_text(git_ov, encoding="utf-8")
    print("written diff files")

# check for missing features in cur vs git
for label, a, b in [("cur", cur, git_h), ("git", git_h, cur)]:
    for k in [
        "li-profile-hero",
        "renderLinkedinHarvestProfileOverview",
        "renderLinkedinPostMetrics",
        "li-metrics-group--posts",
        "Seguidores",
        "linkedinKpiAudienceCount",
    ]:
        if k in a and k not in b:
            print(f"only in {label}: {k}")
        if k not in a and k in b:
            print(f"missing from {label}: {k}")
