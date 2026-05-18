# -*- coding: utf-8 -*-
"""Reorganiza UI: auth/status, analisar vs meu perfil, auto-análise abaixo de Analisar."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD_FORM_BLOCK = """                <motion class="form li-only-form">
                  <motion class="input-wrap no-at" id="profileInputWrap">
                    <input id="profileInput" class="profile" placeholder="https://www.linkedin.com/in/... ou URL da empresa" />
                  </motion>
                  <button type="button" class="btn-analyze" onclick="runLinkedinProfileAnalysis()">Analisar</button>
                </motion>
                <motion class="auth-row li-auth-row">
                  <button type="button" id="btnLinkedinLogin" class="btn-linkedin" onclick="startLinkedInSupabaseLogin()">Login LinkedIn (Supabase)</button>
                  <button type="button" id="btnAutoAnalyze" class="btn-auto-analyze" onclick="runLinkedinAutoProfileAnalysis()" disabled title="Inicia sessão LinkedIn primeiro">Auto-análise</button>
                  <button type="button" id="btnLinkedinLogout" class="btn-logout" onclick="endLinkedInSupabaseSession()" style="display:none">Terminar sessão</button>
                  <span id="linkedinSupabaseStatus" class="badge"><span class="dot"></span> LinkedIn…</span>
                </motion>""".replace("<motion", "<div").replace("motion>", "motion>")

OLD_FORM_BLOCK = """                <motion class="form li-only-form">
                  <motion class="input-wrap no-at" id="profileInputWrap">
                    <input id="profileInput" class="profile" placeholder="https://www.linkedin.com/in/... ou URL da empresa" />
                  </motion>
                  <button type="button" class="btn-analyze" onclick="runLinkedinProfileAnalysis()">Analisar</button>
                </motion>
                <motion class="auth-row li-auth-row">
                  <button type="button" id="btnLinkedinLogin" class="btn-linkedin" onclick="startLinkedInSupabaseLogin()">Login LinkedIn (Supabase)</button>
                  <button type="button" id="btnAutoAnalyze" class="btn-auto-analyze" onclick="runLinkedinAutoProfileAnalysis()" disabled title="Inicia sessão LinkedIn primeiro">Auto-análise</button>
                  <button type="button" id="btnLinkedinLogout" class="btn-logout" onclick="endLinkedInSupabaseSession()" style="display:none">Terminar sessão</button>
                  <span id="linkedinSupabaseStatus" class="badge"><span class="dot"></span> LinkedIn…</span>
                </motion>"""

# fix - use exact div tags from file
OLD_FORM_BLOCK = (
    '                <div class="form li-only-form">\n'
    '                  <div class="input-wrap no-at" id="profileInputWrap">\n'
    '                    <input id="profileInput" class="profile" placeholder="https://www.linkedin.com/in/... ou URL da empresa" />\n'
    "                  </motion>\n"
)

# Read exact from file via search
start = h.find('<div class="form li-only-form">')
end = h.find('<motion id="result"', start)
if end < 0:
    end = h.find('<div id="result"', start)
if start < 0 or end < 0:
    raise SystemExit(f"form block not found start={start} end={end}")

OLD_FORM_BLOCK = h[start:end]

NEW_FORM_BLOCK = """                <div class="hero-layout">
                  <div class="hero-main">
                    <p class="field-label">Analisar outro perfil (URL público)</p>
                    <motion class="form li-analyze-form">
                      <motion class="input-wrap no-at">
                        <input id="profileInput" class="profile" placeholder="https://www.linkedin.com/in/nome ou /company/empresa" />
                      </motion>
                      <div class="analyze-actions">
                        <button type="button" class="btn-analyze" onclick="runLinkedinProfileAnalysis()">Analisar</button>
                        <button type="button" id="btnAutoAnalyze" class="btn-auto-analyze" onclick="runLinkedinAutoProfileAnalysis()" disabled title="Guarda o teu perfil abaixo e inicia sessão">Auto-análise</button>
                      </div>
                    </motion>

                    <p class="field-label" style="margin-top:16px">O meu perfil LinkedIn (guardado na base de dados)</p>
                    <motion class="form li-my-profile-form">
                      <motion class="input-wrap no-at">
                        <input id="myProfileInput" class="profile" placeholder="https://www.linkedin.com/in/o-teu-nome" />
                      </motion>
                      <button type="button" id="btnSaveMyProfile" class="btn-save-profile" onclick="saveMyLinkedinProfileToDatabase()" disabled>Guardar na base de dados</button>
                    </motion>
                    <p id="myProfileSaveHint" class="field-hint">Inicia sessão para associar o teu perfil à conta.</p>
                  </motion>

                  <motion class="hero-auth">
                    <button type="button" id="btnLinkedinLogin" class="btn-linkedin btn-linkedin-block" onclick="startLinkedInSupabaseLogin()">Login LinkedIn (Supabase)</button>
                    <motion class="auth-status-col" id="authStatusCol" style="display:none">
                      <span id="linkedinSupabaseStatus" class="badge ok"><span class="dot"></span> Autenticado</span>
                      <button type="button" id="btnLinkedinLogout" class="btn-logout btn-logout-block" onclick="endLinkedInSupabaseSession()">Terminar sessão</button>
                    </motion>
                  </motion>
                </motion>
"""

NEW_FORM_BLOCK = NEW_FORM_BLOCK.replace("<motion", "<motion").replace("motion>", "motion>")
NEW_FORM_BLOCK = NEW_FORM_BLOCK.replace("<motion", "<div").replace("</motion>", "</div>")

if OLD_FORM_BLOCK not in h:
    raise SystemExit("OLD_FORM_BLOCK not in h")

h = h.replace(OLD_FORM_BLOCK, NEW_FORM_BLOCK)

# CSS additions
CSS_ANCHOR = ".li-only-form { grid-template-columns: 1fr auto; }"
CSS_NEW = """              .hero-layout {
                margin-top: 18px;
                display: grid;
                grid-template-columns: 1fr minmax(200px, 240px);
                gap: 20px;
                align-items: start;
              }
              .hero-main { min-width: 0; }
              .hero-auth {
                display: flex;
                flex-direction: column;
                gap: 10px;
              }
              .field-label {
                margin: 0 0 8px;
                font-size: 0.82rem;
                font-weight: 600;
                color: var(--muted-soft);
                text-transform: uppercase;
                letter-spacing: 0.06em;
              }
              .field-hint {
                margin: 8px 0 0;
                font-size: 0.8rem;
                color: var(--muted);
              }
              .li-analyze-form {
                display: grid;
                grid-template-columns: 1fr;
                gap: 10px;
              }
              .li-my-profile-form {
                display: grid;
                grid-template-columns: 1fr auto;
                gap: 10px;
              }
              .analyze-actions {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
              }
              .analyze-actions .btn-analyze,
              .analyze-actions .btn-auto-analyze {
                width: 100%;
              }
              .auth-status-col {
                display: flex;
                flex-direction: column;
                gap: 8px;
                align-items: stretch;
              }
              .auth-status-col .badge {
                justify-content: center;
                padding: 10px 12px;
                font-size: 0.85rem;
              }
              .btn-linkedin-block,
              .btn-logout-block {
                width: 100%;
                text-align: center;
              }
              .btn-save-profile {
                background: rgba(56,189,248,0.15);
                border: 1px solid rgba(56,189,248,0.35);
                color: var(--accent);
                white-space: nowrap;
              }
              .btn-save-profile:disabled { opacity: 0.45; cursor: not-allowed; }
              @media (max-width: 780px) {
                .hero-layout { grid-template-columns: 1fr; }
                .li-my-profile-form { grid-template-columns: 1fr; }
                .analyze-actions { grid-template-columns: 1fr; }
              }
              .li-only-form { grid-template-columns: 1fr auto; }"""

if ".hero-layout" not in h:
    h = h.replace(CSS_ANCHOR, CSS_NEW)

# Script: myProfileInput reference
if "const myProfileInput" not in h:
    h = h.replace(
        'const profileInput = document.getElementById("profileInput");',
        'const profileInput = document.getElementById("profileInput");\n'
        '              const myProfileInput = document.getElementById("myProfileInput");\n'
        '              const btnSaveMyProfile = document.getElementById("btnSaveMyProfile");\n'
        '              const authStatusCol = document.getElementById("authStatusCol");',
    )

# updateLinkedinAuthButtons - also enable save button
OLD_AUTH_BTNS = """              function updateLinkedinAuthButtons(hasSession) {
                const loginBtn = document.getElementById("btnLinkedinLogin");
                const logoutBtn = document.getElementById("btnLinkedinLogout");
                if (loginBtn) loginBtn.style.display = hasSession ? "none" : "";
                if (logoutBtn) logoutBtn.style.display = hasSession ? "" : "none";
                updateAutoAnalyzeButton(hasSession);
              }"""

NEW_AUTH_BTNS = """              function updateLinkedinAuthButtons(hasSession) {
                const loginBtn = document.getElementById("btnLinkedinLogin");
                const statusCol = document.getElementById("authStatusCol");
                if (loginBtn) loginBtn.style.display = hasSession ? "none" : "";
                if (statusCol) statusCol.style.display = hasSession ? "flex" : "none";
                if (btnSaveMyProfile) btnSaveMyProfile.disabled = !hasSession;
                updateAutoAnalyzeButton(hasSession);
              }

              async function saveMyLinkedinProfileToDatabase() {
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx) {
                  alert("Inicia sessão com Login LinkedIn (Supabase) para guardar o teu perfil.");
                  return;
                }
                const url = (myProfileInput && myProfileInput.value.trim()) || "";
                if (!url) {
                  alert("Cola o URL público do teu perfil LinkedIn (ex.: https://www.linkedin.com/in/o-teu-nome/).");
                  return;
                }
                const hint = document.getElementById("myProfileSaveHint");
                if (hint) hint.textContent = "A guardar…";
                const ok = await saveLinkedinProfileToDatabase(ctx.session, url);
                if (ok) {
                  saveLinkedinProfileUrl(url);
                  if (hint) hint.textContent = "Perfil guardado. A Auto-análise vai usar este URL.";
                } else {
                  if (hint) hint.textContent = "Erro ao guardar. Executaste a migration SQL no Supabase?";
                  alert("Não foi possível guardar. Confirma migrations/001_user_linkedin_profiles.sql no Supabase.");
                }
              }"""

if OLD_AUTH_BTNS in h:
    h = h.replace(OLD_AUTH_BTNS, NEW_AUTH_BTNS)

# loadLinkedinProfileForSession - fill myProfileInput
h = h.replace(
    "if (dbUrl && profileInput) {\n"
    "                  profileInput.value = dbUrl;\n"
    "                  saveLinkedinProfileUrl(dbUrl);\n"
    "                  profileInput.placeholder = \"Perfil da tua conta (base de dados) — podes analisar outros URLs\";\n"
    "                  return dbUrl;\n"
    "                }\n"
    "                applyStoredLinkedinProfileUrl();",
    "if (dbUrl && myProfileInput) {\n"
    "                  myProfileInput.value = dbUrl;\n"
    "                  saveLinkedinProfileUrl(dbUrl);\n"
    "                  const hint = document.getElementById(\"myProfileSaveHint\");\n"
    "                  if (hint) hint.textContent = \"Perfil carregado da base de dados.\";\n"
    "                  return dbUrl;\n"
    "                }\n"
    "                if (myProfileInput) {\n"
    "                  const stored = getStoredLinkedinProfileUrl();\n"
    "                  if (stored && !myProfileInput.value.trim()) myProfileInput.value = stored;\n"
    "                }",
)

# runLinkedinProfileAnalysis - don't use stored in profileInput for analyze others
h = h.replace(
    "const storedUrl = getStoredLinkedinProfileUrl();\n"
    "                  if (storedUrl && !profileValue) profileValue = storedUrl;\n"
    "                  if (autoAuthenticated || !profileValue) {",
    "if (autoAuthenticated || !profileValue) {",
)

# autoAuthenticated block - use myProfileInput
OLD_AUTO_BLOCK = """                  const storedUrl = getStoredLinkedinProfileUrl();
                  if (storedUrl && !profileValue) profileValue = storedUrl;
                  if (!profileValue) {
                    await tryResolveLinkedinProfileUrl(ctx.sb);
                    profileValue = profileInput ? profileInput.value.trim() : "";
                  }
                  if (!profileValue) {
                    useSessionProfile = true;
                  }"""

NEW_AUTO_BLOCK = """                  let myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  if (!myUrl) {
                    await loadLinkedinProfileForSession(ctx.session);
                    myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  }
                  if (!myUrl) {
                    await tryResolveLinkedinProfileUrl(ctx.sb);
                    myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  }
                  if (myUrl) {
                    profileValue = myUrl;
                    useSessionProfile = false;
                  } else {
                    profileValue = "";
                    useSessionProfile = true;
                  }"""

if OLD_AUTO_BLOCK in h:
    h = h.replace(OLD_AUTO_BLOCK, NEW_AUTO_BLOCK)

# refreshLinkedinSupabaseSession status text
h = h.replace(
    'el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn Supabase: " + escapeHtml(String(label));',
    'el.innerHTML = "<span class=\\"dot\\"></span> Autenticado · " + escapeHtml(String(label));',
)
h = h.replace(
    'el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn: sem sessão";',
    'el.innerHTML = "<span class=\\"dot\\"></span> Não autenticado";',
)
h = h.replace(
    'el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn: não configurado";',
    'el.innerHTML = "<span class=\\"dot\\"></span> Supabase não configurado";',
)
h = h.replace(
    'el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn: erro de sessão";',
    'el.innerHTML = "<span class=\\"dot\\"></span> Erro de sessão";',
)
h = h.replace(
    'el.innerHTML = "<span class=\\"dot\\"></span> LinkedIn: indisponível";',
    'el.innerHTML = "<span class=\\"dot\\"></span> Indisponível";',
)

# endLinkedInSupabaseSession - clear myProfileInput hint
h = h.replace(
    "if (profileInput) {\n                  profileInput.value = \"\";\n"
    '                  profileInput.placeholder = "https://www.linkedin.com/in/... ou URL da empresa";',
    "if (profileInput) {\n                  profileInput.value = \"\";\n"
    '                  profileInput.placeholder = "https://www.linkedin.com/in/nome ou /company/empresa";\n'
    "                }\n"
    "                if (myProfileInput) {\n"
    "                  myProfileInput.value = \"\";\n"
    "                }\n"
    "                const hintEl = document.getElementById(\"myProfileSaveHint\");\n"
    "                if (hintEl) hintEl.textContent = \"Inicia sessão para associar o teu perfil à conta.\";\n"
    "                if (false && profileInput) {\n                  profileInput.value = \"\";"
)

# fix botched replace - read and fix endLinkedIn manually
if "if (false && profileInput)" in h:
    h = h.replace(
        "                if (false && profileInput) {\n                  profileInput.value = \"\";",
        "",
    )

# tryResolve - update myProfileInput not profileInput
h = h.replace(
    "if (res.ok && json.profile_url) {\n                    profileInput.value = json.profile_url;",
    "if (res.ok && json.profile_url) {\n                    if (myProfileInput) myProfileInput.value = json.profile_url;",
)

# remove duplicate profileInput placeholder update in refresh
h = h.replace(
    "if (profileInput) {\n                      profileInput.placeholder = \"A obter URL do perfil… ou cola manualmente\";\n                      await tryResolveLinkedinProfileUrl(sb);\n                    }",
    "await tryResolveLinkedinProfileUrl(sb);",
)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "myProfileInput" in h, "hero-layout" in h, "saveMyLinkedinProfileToDatabase" in h)
