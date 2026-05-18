# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

fn = h.find("async function runLinkedinProfileAnalysis")
print("fn at", fn)
chunk = h[fn:fn+25000]
# find result.innerHTML = ` for success (not error)
positions = []
pos = 0
while True:
    i = chunk.find("result.innerHTML = `", pos)
    if i < 0: break
    positions.append(i)
    pos = i + 1
print("result.innerHTML assignments:", positions)
for p in positions:
    print("  ", repr(chunk[p:p+80]))

# find if panel-actions is in chunk before first premature script end
pa = chunk.find("panel-actions")
pe = chunk.find("panel-evolution")
print("panel-actions in fn chunk:", pa, "panel-evolution:", pe)

# Where does chunk end relative to first </script>
first_script = h.find("</script>", fn)
print("first </script> after fn at", first_script - fn, "from global", first_script)
print("between panel-evolution and first script:")
if pe >= 0:
    print(repr(chunk[pe:pe+500]))
    print("...")
    print(repr(h[first_script-200:first_script+50]))
