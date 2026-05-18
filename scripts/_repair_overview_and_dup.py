# -*- coding: utf-8 -*-
import json,re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

# Fix corrupted div between overview and actions
h = re.sub(
    r"</motion>\s*<div\s*<div\s*id=\"panel-actions\"",
    "</div>\n\n                    <div id=\"panel-actions\"",
    h,
)
h = re.sub(
    r"</div>\s*<motion\s*<div\s*id=\"panel-actions\"",
    "</div>\n\n                    <div id=\"panel-actions\"",
    h,
)
h = re.sub(
    r"</div>\s+<div\s+<div\s+id=\"panel-actions\"",
    "</motion>\n\n                    <div id=\"panel-actions\"",
    h,
)
# more patterns
for pat, rep in [
    (r"</div>\s+<div\s+<div id=\"panel-actions\"", "</div>\n\n                    <div id=\"panel-actions\""),
    (r"</div>\s+<div <div id=\"panel-actions\"", "</div>\n\n                    <div id=\"panel-actions\""),
    ("</div>\n\n                                        <div <motion id=\"panel-actions\"", "</div>\n\n                    <div id=\"panel-actions\""),
    ("</div>\n\n                                        <div <div id=\"panel-actions\"", "</div>\n\n                    <div id=\"panel-actions\""),
]:
    h = re.sub(pat, rep, h) if pat.startswith("</") and pat[1] != "d" else h.replace(pat, rep)

# Remove duplicate reset function (keep first complete one)
marker = "function resetLinkedinPostsAfterAnalysis"
positions = []
pos = 0
while True:
    i = h.find(marker, pos)
    if i < 0:
        break
    positions.append(i)
    pos = i + 1
if len(positions) > 1:
    second = positions[1]
    end = h.find("function linkedinPostTypeLabel", second)
    if end > second:
        h = h[:second] + h[end:]

# Clean evolution panel trailing backtick whitespace
h = h.replace("                    </div>\n                                    `;", "                    </div>\n                  `;")

h = h.replace("                    </motion>\n\n                    <motion id=\"panel-actions\"", "                    </div>\n\n                    <div id=\"panel-actions\"")
h = h.replace("                    </motion>\n\n                    <div id=\"panel-actions\"", "                    </div>\n\n                    <motion id=\"panel-actions\"")
h = h.replace("                    </motion>\n\n                    <div id=\"panel-actions\"", "                    </div>\n\n                    <div id=\"panel-actions\"")
# fix stray closing motion tag
h = h.replace("                      </div>\n                    </motion>\n\n                    <div id=\"panel-actions\"",
              "                      </div>\n                    </div>\n\n                    <div id=\"panel-actions\"")

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("dup reset:", h.count("function resetLinkedinPostsAfterAnalysis"))
print("broken div:", "<div <div" in h or "<div <motion" in h)
i = h.find("panel-overview")
print(h[i:i+1450][-200:])
