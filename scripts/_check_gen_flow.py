import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
for s in ["resetLinkedinPostsAfterAnalysis", "generateLinkedinPostsFromSnapshot();", "attachTabHandlers", "btnGenerateLinkedinPosts", "Gerar posts"]:
    print(s, h.count(s))
i = h.find("attachTabHandlers();")
print(h[i:i+400])
i2 = h.find("async function generateLinkedinPostsFromSnapshot")
print("\n---\n", h[i2:i2+900])
