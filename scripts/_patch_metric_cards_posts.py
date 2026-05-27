# -*- coding: utf-8 -*-
"""Usa cartões expansíveis também em «Desempenho das publicações»."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD = """                    ${entries.map(([k, v]) => {
                      const missing = isMetricValueMissing(v);
                      const cls = linkedinMetricCardClasses(k, v, missing);
                      const title = missing
                        ? "O LinkedIn não expõe este dado publicamente ou o scraper não o devolveu."
                        : "";
                      const valueHtml = renderLinkedinMetricValueHtml(k, v, missing, pageKind);
                      return `
                        <div class="${cls}" title="${escapeHtml(title)}">
                          <div class="li-metric-value">${valueHtml}</div>
                          <div class="li-metric-label">${escapeHtml(humanizeMetricKey(k, pageKind))}</div>
                        </div>
                      `;
                    }).join("")}"""

NEW = """                    ${entries.map(([k, v]) => renderLinkedinProfileGridCard(k, v, pageKind)).join("")}"""

if OLD not in h:
    raise SystemExit("renderLinkedinMetricCards map not found")
h = h.replace(OLD, NEW, 1)

# Melhorar fecho do modal de métricas quando calendário também aberto
OLD_CLOSE = """                if (!linkedinCalendarModalDateKey) document.body.style.overflow = \"\";
              }

              function renderLinkedinProfileGridCard"""
NEW_CLOSE = """                const calModal = document.getElementById("linkedinCalendarModal");
                const calOpen = calModal && calModal.classList.contains("open");
                if (!linkedinCalendarModalDateKey && !calOpen) document.body.style.overflow = "";
              }

              function renderLinkedinProfileGridCard"""

if OLD_CLOSE in h:
    h = h.replace(OLD_CLOSE, NEW_CLOSE, 1)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "renderLinkedinProfileGridCard(k, v, pageKind)" in h.split("renderLinkedinMetricCards")[1][:800])
