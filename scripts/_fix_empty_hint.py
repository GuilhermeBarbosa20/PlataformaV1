import json
from pathlib import Path
PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
h = h.replace(
    "Clica <strong>Login LinkedIn (Supabase)</strong> e depois <strong>Auto-análise</strong> ou <strong>Analisar</strong>",
    "Faz <strong>Login</strong>, guarda o <strong>teu perfil</strong> na base de dados e usa <strong>Auto-análise</strong>; para outros perfis, cola o URL em cima e clica <strong>Analisar</strong>",
)
PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
