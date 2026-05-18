# -*- coding: utf-8 -*-
"""Canonicaliza URL LinkedIn no frontend; tryResolve não sobrescreve perfil da BD."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

CANON_FN = """
              function canonicalizeLinkedinProfileUrl(raw) {
                const s = String(raw || "").trim();
                if (!s) return "";
                const noHash = s.split("#")[0].trim();
                let m = noHash.match(/linkedin\\.com\\/in\\/([a-zA-Z0-9\\-_%]+)/i);
                if (m && m[1]) return "https://www.linkedin.com/in/" + decodeURIComponent(m[1]).replace(/\\/$/, "");
                m = noHash.match(/linkedin\\.com\\/company\\/([a-zA-Z0-9\\-_%]+)/i);
                if (m && m[1]) return "https://www.linkedin.com/company/" + decodeURIComponent(m[1]).replace(/\\/$/, "");
                if (!/^https?:\\/\\//i.test(noHash) && !/linkedin\\.com/i.test(noHash)) {
                  const slug = noHash.replace(/^\\/+/, "");
                  if (slug) return "https://www.linkedin.com/in/" + slug;
                }
                if (/linkedin\\.com\\/(in|company)\\//i.test(noHash)) {
                  return noHash.replace(/\\/$/, "");
                }
                return "";
              }

"""

if "function canonicalizeLinkedinProfileUrl" not in h:
    h = h.replace(
        "              function saveLinkedinProfileUrl(url) {",
        CANON_FN + "              function saveLinkedinProfileUrl(url) {",
        1,
    )

# saveLinkedinProfileUrl - use canonical
h = h.replace(
    """              function saveLinkedinProfileUrl(url) {
                const u = String(url || "").trim();
                if (!u || !/linkedin\\.com\\/(in|company)\\//i.test(u)) return;""",
    """              function saveLinkedinProfileUrl(url) {
                const u = canonicalizeLinkedinProfileUrl(url);
                if (!u) return;""",
)

# tryResolve - don't overwrite myProfileInput if already set
OLD_TRY = """                  if (res.ok && json.profile_url) {
                    if (myProfileInput) myProfileInput.value = json.profile_url;
                    saveLinkedinProfileUrl(json.profile_url);
                    profileInput.placeholder = "URL do perfil detectado — podes editar ou clicar Analisar";
                  }"""

NEW_TRY = """                  if (res.ok && json.profile_url) {
                    const resolved = canonicalizeLinkedinProfileUrl(json.profile_url) || json.profile_url;
                    if (myProfileInput && !myProfileInput.value.trim()) {
                      myProfileInput.value = resolved;
                    }
                    if (resolved) saveLinkedinProfileUrl(resolved);
                    if (profileInput) {
                      profileInput.placeholder = "https://www.linkedin.com/in/nome ou /company/empresa";
                    }
                  }"""

if OLD_TRY in h:
    h = h.replace(OLD_TRY, NEW_TRY, 1)

# runLinkedinProfileAnalysis - canonicalize profileValue before send
h = h.replace(
    "                let profileValue = profileInput ? profileInput.value.trim() : \"\";",
    "                let profileValue = profileInput ? profileInput.value.trim() : \"\";\n"
    "                if (profileValue) profileValue = canonicalizeLinkedinProfileUrl(profileValue) || profileValue;",
    1,
)

# auto-analyze myUrl canonicalize
h = h.replace(
    "                  if (myUrl) {\n                    profileValue = myUrl;",
    "                  if (myUrl) {\n"
    "                    myUrl = canonicalizeLinkedinProfileUrl(myUrl) || myUrl;\n"
    "                    if (myProfileInput) myProfileInput.value = myUrl;\n"
    "                    profileValue = myUrl;",
    1,
)

# save my profile
if "saveMyLinkedinProfileToDatabase" in h and "canonicalizeLinkedinProfileUrl(myProfileInput" not in h:
    h = h.replace(
        "const url = myProfileInput ? myProfileInput.value.trim() : \"\";",
        "let url = myProfileInput ? myProfileInput.value.trim() : \"\";\n"
        "                url = canonicalizeLinkedinProfileUrl(url) || url;",
        1,
    )

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok",
      "canonicalizeLinkedinProfileUrl" in h,
      "canonicalizeLinkedinProfileUrl(profileValue)" in h or "canonicalizeLinkedinProfileUrl(profileValue)" in h,
      "myProfileInput.value.trim())" in h.split("tryResolve")[1][:800] if "tryResolve" in h else False)
