# -*- coding: utf-8 -*-
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

h = h.replace(
    "function deleteLinkedinPost(id, scope) {",
    "async function deleteLinkedinPost(id, scope) {",
    1,
)

h = h.replace(
    """function attachTabHandlers() {
                document.querySelectorAll(".tab").forEach(tab => {
                  tab.addEventListener("click", () => {
                    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
                    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
                    tab.classList.add("active");
                    const target = tab.getAttribute("data-target");
                    const panel = document.getElementById("panel-" + target);
                    if (panel) panel.classList.add("active");
                  });
                });
              }""",
    """function attachTabHandlers() {
                document.querySelectorAll(".tab").forEach(tab => {
                  tab.addEventListener("click", () => {
                    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
                    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
                    tab.classList.add("active");
                    const target = tab.getAttribute("data-target");
                    const panel = document.getElementById("panel-" + target);
                    if (panel) panel.classList.add("active");
                    if (target === "calendar") loadLinkedinCalendarPostsFromDatabase();
                  });
                });
              }""",
    1,
)

h = h.replace(
    "if (!res.ok) throw new Error(json.detail || JSON.stringify(json));",
    "if (!res.ok) throw new Error(formatLinkedinApiError(json));",
    1,
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "async function deleteLinkedinPost" in h, 'target === "calendar"' in h)
