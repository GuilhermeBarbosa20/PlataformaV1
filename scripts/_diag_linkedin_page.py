# -*- coding: utf-8 -*-
import json,re
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

patterns = [
    "A gerar posts",
    "generateLinkedinPostsFromSnapshot()",
    "resetLinkedinPostsAfterAnalysis",
    "acoes_prioritarias",
    "plano_crescimento",
    "data-target=\"evolution\"",
    "data-target=\"actions\"",
    "linkedinPostsContainer",
    "<motion",
]
for p in patterns:
    print(p, h.count(p))

# show posts section HTML
i = h.find("Posts para publicar")
print("\n--- posts section ---")
print(h[i:i+800])

# show tab evolution
j = h.find('data-target="evolution"')
print("\n--- evolution tab area ---")
print(h[j:j+1200] if j>=0 else "NOT FOUND")

# show analysis result template for actions
k = h.find("acoes_prioritarias")
print("\n--- first acoes_prioritarias ---")
print(h[k-200:k+400])

# generate function
m = h.find("async function generateLinkedinPostsFromSnapshot")
print("\n--- generate fn ---")
print(h[m:m+1800])

# after analysis
n = h.find("setLinkedinAnalysisSnapshot")
print("\n--- snapshot calls ---")
for match in re.finditer("setLinkedinAnalysisSnapshot", h):
    start = max(0, match.start()-50)
    print(h[start:match.start()+120])
    print("---")
