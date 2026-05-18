# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

# Find all occurrences of acoes_prioritarias
pos = 0
while True:
    i = h.find("acoes_prioritarias", pos)
    if i < 0: break
    script_before = h.rfind("<script", 0, i)
    script_close = h.rfind("</script>", 0, i)
    in_script = script_before > script_close
    print(f"@{i} in_script={in_script} ctx={repr(h[i-80:i+60])}")
    pos = i + 1

# Find </script> tags and check body content between them
print("\n--- script tags ---")
pos = 0
scripts = []
while True:
    i = h.find("<script", pos)
    if i < 0: break
    j = h.find("</script>", i)
    scripts.append((i, j))
    pos = j + 1
print(f"count {len(scripts)}")
for n, (a,b) in enumerate(scripts):
    print(f"  script {n}: {a}-{b} len={b-a}")

# Body between </head> and first script - any ${ ?
body_start = h.find("<body")
first_script = h.find("<script")
body = h[body_start:first_script]
print("\nbody before first script has ${:", "${" in body)
if "${" in body:
    print(repr(body[body.find("${")-50:body.find("${")+200]))

# Check for unclosed script - text after last </script>
last_script_end = h.rfind("</script>")
after = h[last_script_end+9:last_script_end+500]
print("\nafter last script:", repr(after[:300]))

# Static sections in HTML (not in JS string)
for label in ["Ações Prioritárias", "Plano de Crescimento", "listSection"]:
    i = h.find(label)
    while i >= 0:
        in_script = h.rfind("<script", 0, i) > h.rfind("</script>", 0, i)
        if not in_script:
            print(f"STATIC HTML: {label} at {i}: {repr(h[i:i+120])}")
        i = h.find(label, i+1)
