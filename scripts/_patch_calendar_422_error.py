# -*- coding: utf-8 -*-
"""Corrige erro 422 (count>6) e mensagem [object Object] no calendário."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

HELPER = r"""
              function formatLinkedinApiError(json) {
                const d = json && json.detail;
                if (typeof d === "string") return d;
                if (Array.isArray(d)) {
                  return d.map((x) => {
                    if (!x || typeof x !== "object") return String(x);
                    const loc = Array.isArray(x.loc) ? x.loc.join(".") : "";
                    return x.msg ? (loc ? loc + ": " + x.msg : x.msg) : JSON.stringify(x);
                  }).join("; ");
                }
                if (d && typeof d === "object") return d.msg || JSON.stringify(d);
                return json && json.error ? String(json.error) : "Pedido inválido.";
              }
"""

if "function formatLinkedinApiError" not in h:
    anchor = "async function linkedinFetchGeneratedPosts(count) {"
    if anchor not in h:
        raise SystemExit("linkedinFetchGeneratedPosts not found")
    h = h.replace(anchor, HELPER.strip() + "\n\n              " + anchor, 1)

h = h.replace(
    "if (!res.ok) throw new Error(json.detail || JSON.stringify(json));",
    "if (!res.ok) throw new Error(formatLinkedinApiError(json));",
    1,
)

ERR_SNIP = 'el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;'
ERR_FIX = 'el.innerHTML = `<div class="err">Erro: ${escapeHtml(e && e.message ? e.message : String(e))}</div>`;'
h = h.replace(ERR_SNIP, ERR_FIX)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "formatLinkedinApiError" in h)
