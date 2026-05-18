# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

# Find result.innerHTML = ` pattern and check backticks balance in runLinkedinProfileAnalysis
idx = h.find("async function runLinkedinProfileAnalysis")
chunk = h[idx:idx+50000] if idx >= 0 else h

# Find template assignment
ti = chunk.find("result.innerHTML = `")
if ti >= 0:
    sub = chunk[ti:]
    # count backticks until we find closing `;
    depth = 0
    pos = len("result.innerHTML = `")
    while pos < len(sub):
        if sub[pos] == "`" and (pos == 0 or sub[pos-1] != "\\"):
            # check if next is ; or newline+;
            rest = sub[pos:pos+5]
            if rest.startswith("`;") or rest.startswith("`\n"):
                print("Template closes at offset", pos, "snippet:", repr(sub[pos-30:pos+10]))
                break
        pos += 1
    else:
        print("NO CLOSING BACKTICK FOUND in first 50k")
    print("Template start:", repr(sub[:200]))
    print("Around expected end (panel-evolution):")
    pe = sub.find("panel-evolution")
    print(repr(sub[pe:pe+800]))
    print("---")
    # find attachTabHandlers in sub
    ah = sub.find("attachTabHandlers")
    print("attachTabHandlers at", ah, "context:", repr(sub[ah-100:ah+200]))

# Check if ${listSection appears OUTSIDE script (in body as text)
body_end = h.find("</body>")
body = h[:body_end] if body_end > 0 else h
# sections that should only be inside template
for s in ["${listSection(data.acoes_prioritarias)}", "attachTabHandlers();", "profileInput.addEventListener"]:
    i = h.find(s)
    # find if inside <script>
    script_before = h.rfind("<script", 0, i)
    script_close_before = h.rfind("</script>", 0, i)
    in_script = script_before > script_close_before
    print(f"{s[:40]}... at {i} in_script={in_script}")

# Look for premature `; that closes template too early
i = h.find("panel-evolution")
print("\nFull context around evolution + after:")
print(h[i-100:i+600])
