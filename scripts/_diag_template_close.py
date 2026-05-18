# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

fn = h.find("async function runLinkedinProfileAnalysis")
chunk = h[fn:]

# success template at result.innerHTML with renderHeader
i = chunk.find("result.innerHTML = `\n                    ${renderHeader")
print("success template at", i)
sub = chunk[i:]
# walk to find closing `;
pos = len("result.innerHTML = `")
backticks = []
while pos < len(sub):
    if sub[pos] == "`" and (pos == 0 or sub[pos-1] != "\\"):
        backticks.append(pos)
        # check for `;
        if sub[pos:pos+2] == "`;":
            print("CLOSES at", pos, "line preview:", repr(sub[pos-80:pos+20]))
            break
    pos += 1
else:
    print("NO CLOSE in chunk, first backticks at:", backticks[:5], "total", len(backticks))

# what's between last panel in script and bootstrap
boot = chunk.find("bootstrapLinkedinPage")
print("\nbootstrap at", boot)
print("before bootstrap (500 chars):", repr(chunk[boot-500:boot]))
