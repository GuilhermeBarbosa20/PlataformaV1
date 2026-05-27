import json
from pathlib import Path

h = json.loads(
    Path("agents/linkedin_perfil_page.py")
    .read_text(encoding="utf-8")
    .split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1]
)

idx = h.find('id="linkedinMetricDetailModal"')
print("=== BEFORE modal (2000 chars) ===")
print(h[max(0, idx - 2000) : idx])
print("\n=== AFTER modal (800 chars) ===")
print(h[idx : idx + 800])

# Is modal inside static body or only in JS template?
body_idx = h.find("<body")
modal_in_static = False
# find first script tag after body
script_idx = h.find("<script", body_idx if body_idx >= 0 else 0)
print("\nbody", body_idx, "first script", script_idx, "modal before first script?", idx < script_idx if script_idx > 0 else "n/a")

# count how many times modal appears
print("modal count", h.count('id="linkedinMetricDetailModal"'))
