# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())
fn = h.find("async function runLinkedinProfileAnalysis")
chunk = h[fn:]
i = chunk.find("result.innerHTML = `\n                    ${renderHeader")
close = i + 4064  # from prev diag
print("After template close:")
print(chunk[close:close+1200])
