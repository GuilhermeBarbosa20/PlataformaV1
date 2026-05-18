"""Corrige JS partido na página LinkedIn (botões login/analisar)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8")
h = json.loads(raw.split("=", 1)[1].strip())

# 1) Chaveta extra que fecha runLinkedinProfileAnalysis antes do await fetch
h = h.replace(
    "                if (linkedinProviderToken) {\n"
    "                  payload.linkedin_provider_token = linkedinProviderToken;\n"
    "                }\n"
    "                                }\n"
    "                const loadingHint = useSessionProfile",
    "                if (linkedinProviderToken) {\n"
    "                  payload.linkedin_provider_token = linkedinProviderToken;\n"
    "                }\n"
    "                const loadingHint = useSessionProfile",
)

# 2) async duplicado
h = h.replace(
    "\n              async \n              async function refreshLinkedinSupabaseSession",
    "\n              async function refreshLinkedinSupabaseSession",
)

# 3) tryResolve após sessão activa
if "await tryResolveLinkedinProfileUrl(sb)" not in h:
    h = h.replace(
        '                    el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn Supabase: " + escapeHtml(String(label));\n'
        "                    if (profileInput) {\n"
        '                      profileInput.placeholder = "A obter URL do perfil… ou cola manualmente";\n',
        '                    el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn Supabase: " + escapeHtml(String(label));\n'
        "                    if (profileInput) {\n"
        '                      profileInput.placeholder = "A obter URL do perfil… ou cola manualmente";\n'
        "                      await tryResolveLinkedinProfileUrl(sb);\n",
    )

# 4) Garantir attachTabHandlers no fim de runLinkedin
if "attachTabHandlers();\n                } catch (err)" not in h:
    h = h.replace(
        "                  attachTabHandlers();\n                } catch (err) {",
        "                  attachTabHandlers();\n                } catch (err) {",
    )
    # se faltar attachTabHandlers antes do catch
    h = re.sub(
        r"(result\.innerHTML = `\s*\$\{renderHeader\(data\}\).*?</motion>`;\s*)(\n\s*\} catch \(err\))",
        r"\1\n                  attachTabHandlers();\2",
        h,
        count=1,
        flags=re.DOTALL,
    )

# fallback: inserir attachTabHandlers se ainda em falta no runLinkedin
run_start = h.find("async function runLinkedinProfileAnalysis")
run_end = h.find("profileInput.addEventListener", run_start)
if run_start >= 0 and run_end > run_start:
    chunk = h[run_start:run_end]
    if "attachTabHandlers();" not in chunk and "attachTabHandlers();" in h:
        chunk_fixed = chunk.replace(
            "                } catch (err) {",
            "                  attachTabHandlers();\n                } catch (err) {",
            1,
        )
        if chunk_fixed != chunk:
            h = h[:run_start] + chunk_fixed + h[run_end:]

# 5) init Supabase code exchange no arranque
if "initSupabaseAuthFromUrl" not in h:
    init = """
              async function initSupabaseAuthFromUrl() {
                if (!SUPABASE_PUBLIC_URL || !SUPABASE_ANON_KEY) return;
                const params = new URLSearchParams(window.location.search);
                const code = params.get("code");
                if (!code) return;
                try {
                  const { createClient } = await import("https://esm.sh/@supabase/supabase-js@2");
                  const sb = createClient(SUPABASE_PUBLIC_URL, SUPABASE_ANON_KEY);
                  await sb.auth.exchangeCodeForSession(code);
                  window.history.replaceState({}, "", window.location.pathname);
                } catch (e) { /* */ }
              }

"""
    h = h.replace(
        "              refreshLinkedinSupabaseSession();",
        init + "              initSupabaseAuthFromUrl();\n              refreshLinkedinSupabaseSession();",
    )

header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
footer = "\n"
(ROOT / "agents" / "linkedin_perfil_page.py").write_text(
    header + json.dumps(h, ensure_ascii=False) + footer,
    encoding="utf-8",
)

# validar: script sem await fora de async (heurística)
script = h[h.find("<script>") : h.find("</script>")]
if "}\n                const loadingHint" in script and "linkedinProviderToken" in script:
    bad = script.find("}\n                                }\n                const loadingHint")
    if bad >= 0:
        raise SystemExit("still has stray brace")

print("fixed linkedin_perfil_page.py")
