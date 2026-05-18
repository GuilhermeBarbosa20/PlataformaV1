# -*- coding: utf-8 -*-
"""Só guarda URL no localStorage na auto-análise (perfil próprio)."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD = (
    "                  const resolvedUrl = data.profile_url\n"
    "                    || (data.public_profile_data && data.public_profile_data.profile_url)\n"
    "                    || (profileInput && profileInput.value.trim());\n"
    "                  if (resolvedUrl) saveLinkedinProfileUrl(resolvedUrl);"
)
NEW = (
    "                  if (autoAuthenticated) {\n"
    "                    const resolvedUrl = data.profile_url\n"
    "                      || (data.public_profile_data && data.public_profile_data.profile_url)\n"
    "                      || (profileInput && profileInput.value.trim());\n"
    "                    if (resolvedUrl) saveLinkedinProfileUrl(resolvedUrl);\n"
    "                  }"
)

if OLD in h:
    h = h.replace(OLD, NEW)
    PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
    print("patched")
else:
    print("skip - block not found")
