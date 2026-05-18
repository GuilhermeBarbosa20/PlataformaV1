# -*- coding: utf-8 -*-
"""Pedir scopes w_member_social no login LinkedIn OIDC."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
_, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD = """                  const { error } = await sb.auth.signInWithOAuth({
                    provider: "linkedin_oidc",
                    options: { redirectTo },
                  });"""

NEW = """                  const { error } = await sb.auth.signInWithOAuth({
                    provider: "linkedin_oidc",
                    options: {
                      redirectTo,
                      scopes: "openid profile email w_member_social",
                    },
                  });"""

if OLD in h:
    h = h.replace(OLD, NEW)
    print("scopes added")
elif "w_member_social" in h:
    print("already patched")
else:
    raise SystemExit("anchor not found")

out = (
    '"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.\n\n'
    "O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.\n"
    '"""\n\n'
    "from __future__ import annotations\n\n"
    "LINKEDIN_PERFIL_PAGE_HTML: str = "
    + json.dumps(h, ensure_ascii=False)
    + "\n"
)
PAGE.write_text(out, encoding="utf-8")
