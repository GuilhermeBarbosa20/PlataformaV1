# -*- coding: utf-8
"""Correção definitiva: Analisar = só URL público; Auto-análise = só meu perfil."""

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD_RUN = """              async function runLinkedinProfileAnalysis(options) {
                options = options || {};
                const autoAuthenticated = options.autoAuthenticated === true;
                let profileValue = profileInput ? profileInput.value.trim() : "";
                if (profileValue) profileValue = canonicalizeLinkedinProfileUrl(profileValue) || profileValue;
                const pl = "linkedin";
                let supabaseToken = null;
                let linkedinProviderToken = null;
                let useSessionProfile = false;

                const ctx = await getLinkedinSupabaseSession();
                if (ctx) {
                  captureLinkedinOAuthTokens(ctx.session);
                  supabaseToken = ctx.session.access_token;
                  linkedinProviderToken = getPersistedLinkedinProviderToken(ctx.session);
                }

                if (autoAuthenticated) {
                  if (!ctx) {
                    result.innerHTML = `<motion class="err"><strong>Erro:</strong> Sessão LinkedIn expirada ou inválida. Volta a iniciar sessão.</div>`;
                    updateLinkedinAuthButtons(false);
                    return;
                  }
                  let myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  if (!myUrl) {
                    await loadLinkedinProfileForSession(ctx.session);
                    myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  }
                  if (!myUrl) {
                    await tryResolveLinkedinProfileUrl(ctx.sb);
                    myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  }
                  if (myUrl) {
                    myUrl = canonicalizeLinkedinProfileUrl(myUrl) || myUrl;
                    if (myProfileInput) myProfileInput.value = myUrl;
                    profileValue = myUrl;
                    useSessionProfile = false;
                  } else {
                    profileValue = "";
                    useSessionProfile = true;
                  }
                }

                if (!profileValue && !autoAuthenticated) {
                  result.innerHTML = `<motion class="err"><strong>Erro:</strong> Cola o URL público do perfil que queres analisar (campo «Analisar outro perfil»).</div>`;
                  return;
                }

                const endpoint = "/agents/social-media/profile-analyze";
                const payload = {
                  profile_input: profileValue,
                  messages: [],
                  language: "pt-PT",
                  platform: pl,
                };
                if (autoAuthenticated) {
                  payload.link_as_own_profile = true;
                }
                if (ctx && ctx.session) {
                  appendLinkedinSessionFields(payload, ctx.session, {
                    includeStoredUrl: autoAuthenticated || !profileValue,
                  });
                } else if (supabaseToken) {
                  payload.supabase_access_token = supabaseToken;
                  if (linkedinProviderToken) payload.linkedin_provider_token = linkedinProviderToken;
                  const storedLi = getStoredLinkedinProfileUrl();
                  if (storedLi) payload.stored_linkedin_profile_url = storedLi;
                }"""

NEW_RUN = """              async function runLinkedinProfileAnalysis(options) {
                options = options || {};
                const autoAuthenticated = options.autoAuthenticated === true;
                const ctx = await getLinkedinSupabaseSession();
                if (ctx) captureLinkedinOAuthTokens(ctx.session);

                let profileValue = "";

                if (autoAuthenticated) {
                  if (!ctx || !ctx.session) {
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> Sessão LinkedIn expirada ou inválida. Volta a iniciar sessão.</div>`;
                    updateLinkedinAuthButtons(false);
                    return;
                  }
                  let myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  if (!myUrl) {
                    await loadLinkedinProfileForSession(ctx.session);
                    myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  }
                  if (!myUrl) {
                    await tryResolveLinkedinProfileUrl(ctx.sb);
                    myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  }
                  profileValue = canonicalizeLinkedinProfileUrl(myUrl) || myUrl;
                  if (!profileValue) {
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> Cola o URL do teu perfil em «O meu perfil LinkedIn» e guarda na base de dados, ou inicia sessão de novo.</motion>`;
                    return;
                  }
                  if (myProfileInput) myProfileInput.value = profileValue;
                } else {
                  const rawOther = profileInput ? profileInput.value.trim() : "";
                  profileValue = canonicalizeLinkedinProfileUrl(rawOther) || rawOther;
                  if (!profileValue) {
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> Cola o URL público do perfil em «Analisar outro perfil» (ex.: https://www.linkedin.com/in/nome).</div>`;
                    return;
                  }
                }

                const endpoint = "/agents/social-media/profile-analyze";
                const payload = {
                  profile_input: profileValue,
                  messages: [],
                  language: "pt-PT",
                  platform: "linkedin",
                };

                if (autoAuthenticated) {
                  payload.link_as_own_profile = true;
                  appendLinkedinSessionFields(payload, ctx.session, { includeStoredUrl: true });
                }"""

OLD_RUN = OLD_RUN.replace("<motion class=\"err\">", "<div class=\"err\">").replace("</motion>`;", "</motion>`;")
NEW_RUN = NEW_RUN.replace("<motion class=\"err\">", "<div class=\"err\">").replace("</motion>`;", "</motion>`;")
NEW_RUN = NEW_RUN.replace("base de dados, ou inicia sessão de novo.</motion>`", "base de dados, ou inicia sessão de novo.</div>`")

# Find end of payload setup - loadingHint
if OLD_RUN.replace("motion", "div")[:500] not in h.replace("motion", "motion")[:500]:
    # try without motion fixes
    OLD_START = h.find("async function runLinkedinProfileAnalysis(options)")
    OLD_END = h.find("const loadingHint = autoAuthenticated", OLD_START)
    if OLD_START >= 0 and OLD_END > OLD_START:
        NEW_PART = NEW_RUN + "\n                " + h[OLD_END:OLD_END+800].split("try {")[0]
        h = h[:OLD_START] + NEW_PART + h[OLD_END + len(h[OLD_END:OLD_END+800].split("try {")[0]):]
        print("replaced via slice")
    else:
        print("FAIL slice", OLD_START, OLD_END)
else:
    if OLD_RUN in h:
        h = h.replace(OLD_RUN, NEW_RUN, 1)
        print("replaced exact")
    else:
        OLD_START = h.find("async function runLinkedinProfileAnalysis(options)")
        OLD_END = h.find("const loadingHint = autoAuthenticated", OLD_START)
        NEW_PART = NEW_RUN + "\n                " + h[OLD_END:h.find("try {", OLD_END)]
        h = h[:OLD_START] + NEW_PART + h[h.find("try {", OLD_END):]
        print("replaced slice fallback")

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

# verify
if "autoAuthenticated || !profileValue" in h:
    print("WARN still has old includeStoredUrl logic")
if "appendLinkedinSessionFields(payload, ctx.session, {" in h:
    i = h.find("runLinkedinProfileAnalysis")
    chunk = h[i:i+4000]
    print("auto sends session:", "link_as_own_profile = true" in chunk and "includeStoredUrl: true" in chunk)
    print("manual no session in else:", chunk.count("appendLinkedinSessionFields") == 1)
