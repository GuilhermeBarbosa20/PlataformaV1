# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

for name in ["panel-actions", "panel-evolution", "panel-overview", "panel-content"]:
    i = h.find(f'id="{name}"')
    if i < 0:
        print(name, "NOT FOUND")
        continue
    end = h.find('</div>', i+500)
    # find panel end - look for next panel-
    j = h.find('id="panel-', i+20)
    chunk = h[i:j if j>i else i+2500]
    print(f"\n=== {name} ({len(chunk)} chars) ===")
    print(chunk[:2000])
    if len(chunk)>2000:
        print("...")

# reset function
i = h.find("function resetLinkedinPostsAfterAnalysis")
print("\n=== reset fn ===")
print(h[i:i+600] if i>=0 else "MISSING")

# after analysis hook
i = h.find("resetLinkedinPostsAfterAnalysis()")
print("\n=== reset calls ===", h.count("resetLinkedinPostsAfterAnalysis()"))
for pos in range(len(h)):
    if h.startswith("resetLinkedinPostsAfterAnalysis()", pos):
        print(h[max(0,pos-80):pos+80])
