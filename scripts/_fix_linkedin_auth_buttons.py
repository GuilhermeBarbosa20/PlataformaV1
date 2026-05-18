# -*- coding: utf-8 -*-
"""Garante botões Auto-análise e Terminar sessão no HTML + JS."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD_AUTH_ROW = (
    '<motion class="auth-row li-auth-row">\n'
    '                  <button type="button" class="btn-linkedin" onclick="startLinkedInSupabaseLogin()">Login LinkedIn (Supabase)</button>\n'
    '                  <span id="linkedinSupabaseStatus"'
).replace("<motion", "<motion")

OLD_AUTH_ROW = """<div class="auth-row li-auth-row">
                  <button type="button" class="btn-linkedin" onclick="startLinkedInSupabaseLogin()">Login LinkedIn (Supabase)</button>
                  <span id="linkedinSupabaseStatus\""""

# fix - use exact from file
OLD_AUTH_ROW = (
    '<div class="auth-row li-auth-row">\n'
    '                  <button type="button" class="btn-linkedin" onclick="startLinkedInSupabaseLogin()">Login LinkedIn (Supabase)</button>\n'
    '                  <span id="linkedinSupabaseStatus"'
)

NEW_AUTH_ROW = (
    '<motion class="auth-row li-auth-row">\n'
    '                  <button type="button" id="btnLinkedinLogin" class="btn-linkedin" onclick="startLinkedInSupabaseLogin()">Login LinkedIn (Supabase)</button>\n'
    '                  <button type="button" id="btnAutoAnalyze" class="btn-auto-analyze" onclick="runLinkedinAutoProfileAnalysis()" disabled title="Inicia sessão LinkedIn primeiro">Auto-análise</button>\n'
    '                  <button type="button" id="btnLinkedinLogout" class="btn-logout" onclick="endLinkedInSupabaseSession()" style="display:none">Terminar sessão</button>\n'
    '                  <span id="linkedinSupabaseStatus"'
).replace("<motion", "<div").replace("motion>", "div>")

if OLD_AUTH_ROW not in h:
    raise SystemExit("auth row not found")
h = h.replace(OLD_AUTH_ROW, NEW_AUTH_ROW)

if ".btn-auto-analyze" not in h:
    h = h.replace(
        ".btn-linkedin:disabled { opacity: 0.45; cursor: not-allowed; }",
        ".btn-linkedin:disabled { opacity: 0.45; cursor: not-allowed; }\n"
        "              .btn-auto-analyze {\n"
        "                background: linear-gradient(135deg, #0a66c2, #004182);\n"
        "                border: 1px solid rgba(255,255,255,0.2);\n"
        "                box-shadow: 0 6px 18px rgba(10,102,194,0.35);\n"
        "              }\n"
        "              .btn-auto-analyze:disabled { opacity: 0.45; cursor: not-allowed; filter: none; }\n"
        "              .btn-logout {\n"
        "                background: rgba(255,255,255,0.06);\n"
        "                border: 1px solid var(--line-strong);\n"
        "                color: var(--muted-soft);\n"
        "              }\n"
        "              .btn-logout:hover { color: #fff; border-color: rgba(248,113,113,0.45); }",
    )

LOGOUT_FN = """
              function updateLinkedinAuthButtons(hasSession) {
                const loginBtn = document.getElementById("btnLinkedinLogin");
                const logoutBtn = document.getElementById("btnLinkedinLogout");
                if (loginBtn) loginBtn.style.display = hasSession ? "none" : "";
                if (logoutBtn) logoutBtn.style.display = hasSession ? "" : "none";
                updateAutoAnalyzeButton(hasSession);
              }

              async function endLinkedInSupabaseSession() {
                const sb = await getLinkedinSupabaseClient();
                if (!sb) {
                  updateLinkedinAuthButtons(false);
                  return;
                }
                try {
                  await sb.auth.signOut();
                } catch (e) {
                  console.warn("signOut:", e);
                }
                if (profileInput) {
                  profileInput.value = "";
                  profileInput.placeholder = "https://www.linkedin.com/in/... ou URL da empresa";
                }
                updateLinkedinAuthButtons(false);
                const el = document.getElementById("linkedinSupabaseStatus");
                if (el) {
                  el.className = "badge";
                  el.innerHTML = '<span class="dot"></span> LinkedIn: sem sessão';
                }
              }

"""

if "function updateLinkedinAuthButtons" not in h:
    h = h.replace(
        "function updateAutoAnalyzeButton(hasSession) {",
        LOGOUT_FN + "              function updateAutoAnalyzeButton(hasSession) {",
    )
    # updateAutoAnalyzeButton should also call updateLinkedinAuthButtons OR we replace all updateAutoAnalyzeButton calls with updateLinkedinAuthButtons

# Replace direct updateAutoAnalyzeButton calls in refresh with updateLinkedinAuthButtons
h = h.replace("updateAutoAnalyzeButton(true);", "updateLinkedinAuthButtons(true);")
h = h.replace("updateAutoAnalyzeButton(false);", "updateLinkedinAuthButtons(false);")

# runLinkedinAutoProfileAnalysis still uses updateAutoAnalyzeButton on error - replace
h = h.replace("updateAutoAnalyzeButton(false);", "updateLinkedinAuthButtons(false);")

# bootstrap
h = h.replace(
    'if (!document.getElementById("btnAutoAnalyze")) updateAutoAnalyzeButton(false);',
    "updateLinkedinAuthButtons(false);",
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

# verify
h2 = json.loads(PAGE.read_text(encoding="utf-8").split("=", 1)[1].strip())
checks = ['id="btnAutoAnalyze"', 'id="btnLinkedinLogout"', "endLinkedInSupabaseSession", "Terminar sessão", "updateLinkedinAuthButtons"]
for c in checks:
    print(c, c in h2)
