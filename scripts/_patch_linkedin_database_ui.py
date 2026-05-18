# -*- coding: utf-8 -*-
"""UI: carregar perfil da BD Supabase no login + link_as_own_profile na auto-análise."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

DB_FN = r"""
              async function fetchLinkedinProfileFromDatabase(session) {
                if (!session || !session.access_token) return null;
                try {
                  const res = await fetch("/agents/linkedin/stored-profile", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ supabase_access_token: session.access_token }),
                  });
                  if (res.status === 404) return null;
                  const json = await res.json();
                  if (res.ok && json.profile_url) return json.profile_url;
                } catch (e) {
                  console.warn("fetchLinkedinProfileFromDatabase:", e);
                }
                return null;
              }

              async function saveLinkedinProfileToDatabase(session, profileUrl) {
                if (!session || !session.access_token || !profileUrl) return false;
                try {
                  const res = await fetch("/agents/linkedin/stored-profile", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      supabase_access_token: session.access_token,
                      profile_url: profileUrl,
                    }),
                  });
                  return res.ok;
                } catch (e) {
                  return false;
                }
              }

              async function loadLinkedinProfileForSession(session) {
                const dbUrl = await fetchLinkedinProfileFromDatabase(session);
                if (dbUrl && profileInput) {
                  profileInput.value = dbUrl;
                  saveLinkedinProfileUrl(dbUrl);
                  profileInput.placeholder = "Perfil da tua conta (base de dados) — podes analisar outros URLs";
                  return dbUrl;
                }
                applyStoredLinkedinProfileUrl();
                return profileInput ? profileInput.value.trim() : "";
              }

"""

if "fetchLinkedinProfileFromDatabase" not in h:
    h = h.replace("              function escapeHtml(value) {", DB_FN + "              function escapeHtml(value) {")

# refreshLinkedinSupabaseSession - load from DB
if "loadLinkedinProfileForSession" not in h.split("refreshLinkedinSupabaseSession")[1][:1200]:
    h = h.replace(
        "captureLinkedinOAuthTokens(data.session);\n"
        "                    const u = data.session.user;",
        "captureLinkedinOAuthTokens(data.session);\n"
        "                    await loadLinkedinProfileForSession(data.session);\n"
        "                    const u = data.session.user;",
    )

# initSupabaseAuthFromUrl - load after login
if "loadLinkedinProfileForSession(sessAfter.session)" not in h:
    h = h.replace(
        "captureLinkedinOAuthTokens(sessAfter.session);\n"
        "                  await tryResolveLinkedinProfileUrl(sb);",
        "captureLinkedinOAuthTokens(sessAfter.session);\n"
        "                  await loadLinkedinProfileForSession(sessAfter.session);\n"
        "                  if (!profileInput || !profileInput.value.trim()) {\n"
        "                    await tryResolveLinkedinProfileUrl(sb);\n"
        "                  }",
    )

# payload link_as_own_profile
if "link_as_own_profile" not in h:
    h = h.replace(
        "                if (ctx && ctx.session) {\n"
        "                  appendLinkedinSessionFields(payload, ctx.session);",
        "                if (autoAuthenticated) {\n"
        "                  payload.link_as_own_profile = true;\n"
        "                }\n"
        "                if (ctx && ctx.session) {\n"
        "                  appendLinkedinSessionFields(payload, ctx.session);",
    )

# tryResolve - save to DB on success
if "saveLinkedinProfileToDatabase(session" not in h:
    h = h.replace(
        "saveLinkedinProfileUrl(json.profile_url);\n"
        "                    profileInput.placeholder = \"URL do perfil detectado",
        "saveLinkedinProfileUrl(json.profile_url);\n"
        "                    await saveLinkedinProfileToDatabase(session, json.profile_url);\n"
        "                    profileInput.placeholder = \"URL do perfil detectado",
    )

# subtitle
h = h.replace(
    "Na 1.ª vez cola o URL público do perfil; depois a <strong>Auto-análise</strong> usa o URL guardado.",
    "Na 1.ª vez cola o URL do teu perfil (fica na <strong>base de dados</strong>); depois o login + <strong>Auto-análise</strong> usam-no automaticamente.",
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "fetchLinkedinProfileFromDatabase" in h, "link_as_own_profile" in h)
