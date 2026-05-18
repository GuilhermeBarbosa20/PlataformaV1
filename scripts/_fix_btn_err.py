import json
from pathlib import Path
PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

needle = 'if (el) el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</motion>`;'
if "btnErr.textContent" not in h:
    h = h.replace(
        'if (el) el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;\n                }\n              }\n\n              const profileInput',
        'if (el) el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;\n'
        '                  const btnErr = document.getElementById("btnGenerateLinkedinPosts");\n'
        '                  if (btnErr) { btnErr.disabled = false; btnErr.textContent = "Gerar posts"; }\n'
        "                }\n              }\n\n              const profileInput",
        1,
    )

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("btnErr", "btnErr.textContent" in h)
