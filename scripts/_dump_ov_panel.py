import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML as h

ov = h.split('id="panel-overview"', 1)[1].split('id="panel-posts"', 1)[0]
Path(__file__).parent.joinpath("_ov_panel.txt").write_text(ov, encoding="utf-8")
print("len", len(ov))
print(ov[:2000])
