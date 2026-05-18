# -*- coding: utf-8 -*-
"""Restaura o JS truncado após renderLinkedinMetricCards e aplica métricas LinkedIn."""
from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

MARKER = "              function renderLinkedinMetricCards(obj, ctx) {"
if MARKER not in h:
    raise SystemExit("renderLinkedinMetricCards não encontrada")

if "async function runLinkedinProfileAnalysis" in h:
    raise SystemExit("página já contém runLinkedinProfileAnalysis — abortar")

# Cortar lixo após fecho da função renderLinkedinMetricCards
start_fn = h.find(MARKER)
end_fn = h.find("\n              }", h.rfind("`.replace(/<\\/motion>"))
if end_fn < 0:
    end_fn = h.find("\n              }", h.rfind("li-metric-value"))
if end_fn < 0:
    raise SystemExit("fim de renderLinkedinMetricCards não encontrado")
end_fn += len("\n              }")
h = h[:end_fn]

# CSS is-unavailable
if ".li-metric-card.is-unavailable" not in h:
    h = h.replace(
        ".li-metric-card.is-muted .li-metric-value { color: var(--muted); font-weight: 600; }",
        ".li-metric-card.is-unavailable .li-metric-value {\n"
        "                font-size: 0.72rem;\n"
        "                line-height: 1.35;\n"
        "                font-weight: 500;\n"
        "                color: var(--muted);\n"
        "              }\n"
        "              .li-metric-card.is-muted .li-metric-value { color: var(--muted); font-weight: 600; }",
        1,
    )

# renderKpis: Seguidores em páginas organization
h = h.replace(
    '{ label: "Ligações", value: formatNumber(profile.followers_count), sub: profile.employer ? String(profile.employer).slice(0, 40) : "", accent: true },',
    '{ label: (String(data.profile_url || profile.profile_url || "").toLowerCase().includes("/company/") || String(data.profile_url || profile.profile_url || "").toLowerCase().includes("/school/")) ? "Seguidores" : "Ligações", value: formatNumber(profile.followers_count), sub: profile.employer ? String(profile.employer).slice(0, 40) : "", accent: true },',
)

TAIL = r"""

              function renderCadence(cadence) {
                cadence = cadence || {};
                const pills = [];
                if (cadence.posts_last_30_days !== undefined) pills.push(["Posts (30d)", cadence.posts_last_30_days]);
                if (cadence.avg_days_between_posts !== undefined) pills.push(["Intervalo médio", `${cadence.avg_days_between_posts} dias`]);
                if (cadence.last_post_at) {
                  const d = new Date(cadence.last_post_at);
                  pills.push(["Último post", isNaN(d.getTime()) ? cadence.last_post_at : d.toLocaleDateString("pt-PT")]);
                }
                if (!pills.length) return `<motion class="metric-pills"><span class="metric-pill">Sem datas nas publicações recolhidas.</span></div>`;
                return `
                  <div class="metric-pills">
                    ${pills.map(([k, v]) => `<span class="metric-pill"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(v)}</span>`).join("")}
                  </div>
                `.replace("<motion class=\"metric-pills\">", '<motion class="metric-pills">'.replace("motion", "motion")).replace('</div>`', '</div>`');
              }

              function renderTabs() {
                return `
                  <div class="tabs">
                    <div class="tab active" data-target="overview">Visão Geral</div>
                    <div class="tab" data-target="actions">Ações &amp; Ideias</div>
                    <motion class="tab" data-target="content">Tipos de conteúdo</div>
                    <div class="tab" data-target="evolution">Plano &amp; Ações</motion>
                  </div>
                `.replace(/<motion class="tab"/g, '<div class="tab"').replace("</motion>", "</div>");
              }

              function attachTabHandlers() {
                document.querySelectorAll(".tab").forEach(tab => {
                  tab.addEventListener("click", () => {
                    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
                    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
                    tab.classList.add("active");
                    const target = tab.getAttribute("data-target");
                    const panel = document.getElementById("panel-" + target);
                    if (panel) panel.classList.add("active");
                  });
                });
              }

              let linkedinSupabaseClient = null;

              async function getLinkedinSupabaseClient() {
                if (!SUPABASE_PUBLIC_URL || !SUPABASE_ANON_KEY) return null;
                if (linkedinSupabaseClient) return linkedinSupabaseClient;
                const { createClient } = await import("https://esm.sh/@supabase/supabase-js@2");
                linkedinSupabaseClient = createClient(SUPABASE_PUBLIC_URL, SUPABASE_ANON_KEY, {
                  auth: { detectSessionInUrl: true, persistSession: true, autoRefreshToken: true },
                });
                return linkedinSupabaseClient;
              }

              async function initSupabaseAuthFromUrl() {
                const sb = await getLinkedinSupabaseClient();
                if (!sb) return null;
                const search = window.location.search || "";
                const hash = window.location.hash || "";
                const params = new URLSearchParams(search);
                const code = params.get("code");
                try {
                  if (code) await sb.auth.exchangeCodeForSession(code);
                  else if (hash && (hash.includes("access_token") || hash.includes("refresh_token"))) {
                    await sb.auth.getSession();
                  }
                } catch (e) {
                  console.warn("initSupabaseAuthFromUrl:", e);
                }
                if (code || (hash && hash.includes("access_token"))) {
                  window.history.replaceState({}, "", window.location.pathname);
                }
                return sb;
              }

              async function getLinkedinSupabaseSession() {
                const sb = await getLinkedinSupabaseClient();
                if (!sb) return null;
                const { data, error } = await sb.auth.getSession();
                if (error || !data.session) return null;
                return { sb, session: data.session };
              }

              function updateLinkedinAuthButtons(connected) {
                const loginBtn = document.getElementById("btnLinkedinLogin");
                const col = document.getElementById("authStatusCol");
                const autoBtn = document.getElementById("btnAutoAnalyze");
                const saveBtn = document.getElementById("btnSaveMyProfile");
                if (loginBtn) loginBtn.style.display = connected ? "none" : "";
                if (col) col.style.display = connected ? "flex" : "none";
                if (autoBtn) autoBtn.disabled = !connected;
                if (saveBtn) saveBtn.disabled = !connected;
              }

              function updateAutoAnalyzeButton() {
                const autoBtn = document.getElementById("btnAutoAnalyze");
                if (!autoBtn) return;
                const hasMy = myProfileInput && myProfileInput.value.trim();
                autoBtn.title = hasMy
                  ? "Analisa o teu perfil guardado (sessão + Apify)"
                  : "Guarda o teu perfil abaixo e inicia sessão";
              }

              async function startLinkedInSupabaseLogin() {
                if (!SUPABASE_PUBLIC_URL || !SUPABASE_ANON_KEY) {
                  alert("Supabase não configurado no servidor (.env).");
                  return;
                }
                try {
                  const sb = await getLinkedinSupabaseClient();
                  if (!sb) return;
                  const redirectTo = window.location.origin + window.location.pathname;
                  const { error } = await sb.auth.signInWithOAuth({
                    provider: "linkedin_oidc",
                    options: { redirectTo },
                  });
                  if (error) throw error;
                } catch (e) {
                  alert("Erro no login: " + (e.message || e));
                }
              }

              async function endLinkedInSupabaseSession() {
                try {
                  const sb = await getLinkedinSupabaseClient();
                  if (sb) await sb.auth.signOut();
                  sessionStorage.removeItem(LINKEDIN_PROVIDER_TOKEN_KEY);
                  sessionStorage.removeItem(LINKEDIN_ID_TOKEN_KEY);
                } catch (e) { /* */ }
                updateLinkedinAuthButtons(false);
                updateAutoAnalyzeButton();
              }

              async function refreshLinkedinSupabaseSession() {
                const ctx = await getLinkedinSupabaseSession();
                updateLinkedinAuthButtons(Boolean(ctx));
                if (ctx) {
                  captureLinkedinOAuthTokens(ctx.session);
                  await loadLinkedinProfileForSession(ctx.session);
                  await tryResolveLinkedinProfileUrl(ctx.sb);
                }
                updateAutoAnalyzeButton();
              }

              async function tryResolveLinkedinProfileUrl(sb) {
                if (!sb) return;
                try {
                  const res = await fetch("/agents/linkedin/resolve-profile-url", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(
                      appendLinkedinSessionFields(
                        { messages: [], language: "pt-PT", platform: "linkedin" },
                        (await getLinkedinSupabaseSession())?.session,
                        { includeStoredUrl: true }
                      )
                    ),
                  });
                  const json = await res.json();
                  if (res.ok && json.profile_url && myProfileInput && !myProfileInput.value.trim()) {
                    myProfileInput.value = json.profile_url;
                    saveLinkedinProfileUrl(json.profile_url);
                  }
                } catch (e) {
                  console.warn("tryResolveLinkedinProfileUrl:", e);
                }
              }

              async function saveMyLinkedinProfileToDatabase() {
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx) {
                  alert("Inicia sessão primeiro.");
                  return;
                }
                const url = canonicalizeLinkedinProfileUrl(myProfileInput ? myProfileInput.value.trim() : "");
                if (!url) {
                  alert("URL inválido.");
                  return;
                }
                const ok = await saveLinkedinProfileToDatabase(ctx.session, url);
                const hint = document.getElementById("myProfileSaveHint");
                if (hint) hint.textContent = ok ? "Perfil guardado na base de dados." : "Erro ao guardar. Confirma a migration no Supabase.";
                if (ok) {
                  saveLinkedinProfileUrl(url);
                  updateAutoAnalyzeButton();
                }
              }

              async function runLinkedinProfileAnalysis(options) {
                options = options || {};
                const autoAuthenticated = options.autoAuthenticated === true;
                const ctx = await getLinkedinSupabaseSession();
                if (ctx) captureLinkedinOAuthTokens(ctx.session);

                let profileValue = "";
                if (autoAuthenticated) {
                  if (!ctx || !ctx.session) {
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> Sessão LinkedIn expirada. Volta a iniciar sessão.</div>`;
                    updateLinkedinAuthButtons(false);
                    return;
                  }
                  let myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  if (!myUrl) {
                    await loadLinkedinProfileForSession(ctx.session);
                    myUrl = myProfileInput ? myProfileInput.value.trim() : "";
                  }
                  if (!myUrl) await tryResolveLinkedinProfileUrl(ctx.sb);
                  profileValue = canonicalizeLinkedinProfileUrl(myProfileInput ? myProfileInput.value.trim() : "") || "";
                  if (!profileValue) {
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> Cola o URL do teu perfil em «O meu perfil LinkedIn» e guarda na base de dados.</div>`;
                    return;
                  }
                  if (myProfileInput) myProfileInput.value = profileValue;
                } else {
                  const rawOther = profileInput ? profileInput.value.trim() : "";
                  profileValue = canonicalizeLinkedinProfileUrl(rawOther) || rawOther;
                  if (!profileValue) {
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> Cola o URL público em «Analisar outro perfil».</div>`;
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
                }

                const loadingHint = autoAuthenticated
                  ? "A recolher o teu perfil LinkedIn (sessão + Apify)…"
                  : "LinkedIn (Apify + OpenAI) — pode demorar…";
                result.innerHTML = `
                  <div class="loading">
                    <div class="spinner"></motion>
                    <div>
                      <div style="color: var(--text); font-weight:600">A processar análise</div>
                      <div style="font-size:0.85rem">${escapeHtml(loadingHint)}</div>
                    </div>
                  </div>
                `.replace("<motion class=\"spinner\"></motion>", '<div class="spinner"></div>').replace('</motion>', '</motion>');

                try {
                  const response = await fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    credentials: "same-origin",
                    body: JSON.stringify(payload),
                  });
                  const data = await response.json();
                  if (!response.ok) {
                    const detailText = data.detail || JSON.stringify(data);
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> ${escapeHtml(detailText)}</div>`;
                    return;
                  }

                  setLinkedinAnalysisSnapshot(data);
                  resetLinkedinPostsAfterAnalysis();

                  const profile = data.public_profile_data || {};
                  const enrichment = profile.apify_enrichment || {};

                  result.innerHTML = `
                    ${renderHeader(data)}
                    ${renderKpis(data)}
                    ${renderTabs()}

                    <div id="panel-overview" class="panel active">
                      <div class="section">
                        <h3>Principais Insights <span class="pill cool">IA</span></h3>
                        <ul class="insight-list">${listSection(data.principais_insights)}</ul>
                      </div>
                      <div class="section">
                        <h3>Problemas Identificados <span class="pill">atenção</span></h3>
                        <ul class="insight-list problems">${listSection(data.problemas_identificados)}</ul>
                      </div>
                      <div class="section">
                        <h3>Oportunidades <span class="pill cool">crescimento</span></h3>
                        <ul class="insight-list opps">${listSection(data.oportunidades)}</ul>
                      </div>
                      <div class="section li-metrics-section">
                        <h3>Indicadores de desempenho <span class="pill cool">LinkedIn</span></h3>
                        <p class="section-desc">Resumo quantitativo da página e das publicações analisadas. Campos sem dado público aparecem assinalados.</p>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Métricas específicas (LinkedIn)</h4>
                          ${renderLinkedinMetricCards(data.metricas_linkedin || data.metricas_instagram, data)}
                        </div>
                        <div class="li-metrics-group">
                          <h4 class="li-metrics-group-title">Desempenho geral</h4>
                          ${renderLinkedinMetricCards(data.metricas_universais, data)}
                        </div>
                      </div>
                    </div>

                    <motion id="panel-actions" class="panel">
                      <motion class="section" data-section="acoes-prioritarias">
                        <h3>Ações Prioritárias <span class="pill">agora</span></h3>
                        <ul class="insight-list actions">${listSection(data.acoes_prioritarias)}</ul>
                      </div>
                      <div class="section" data-section="ideias-conteudo">
                        <h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>
                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>
                      </div>
                    </div>

                    <div id="panel-content" class="panel">
                      <div class="section">
                        <h3>Tipos de conteúdo LinkedIn</h3>
                        ${renderFormatBars(enrichment.content_type_distribution || enrichment.format_distribution)}
                      </div>
                      <div class="section">
                        <h3>Top posts <span class="pill cool">reações</span></h3>
                        ${renderTopCards(enrichment.top_posts, "top posts")}
                      </div>
                      <div class="section">
                        <h3>Cadência de publicação</h3>
                        ${renderCadence(enrichment.posting_cadence || {})}
                      </div>
                    </div>

                    <div id="panel-evolution" class="panel">
                      <div class="section" data-section="plano-crescimento">
                        <h3>Plano de Crescimento (curto prazo)</h3>
                        <ul class="insight-list">${listSection(data.plano_crescimento_curto_prazo)}</ul>
                      </div>
                      <div class="section" data-section="posts-publicar">
                        <h3>Posts para publicar <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Gerados com IA a partir da análise. Aprova, edita ou refaz cada post.</p>
                        <motion id="linkedinPostsContainer" class="li-posts-wrap"><motion class="li-posts-loading">Clica em <strong>Gerar posts</strong> para criar publicações com IA.</div></div>
                        <button type="button" class="btn-save-profile" style="margin-top:10px" id="btnGenerateLinkedinPosts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>
                      </div>
                    </div>
                  `;
                  attachTabHandlers();
                  const resolvedUrl = data.profile_url || profile.profile_url || profileValue;
                  if (resolvedUrl && autoAuthenticated) saveLinkedinProfileUrl(resolvedUrl);
                } catch (err) {
                  const errorMessage = err instanceof Error ? err.message : String(err);
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> ${escapeHtml(errorMessage)}</div>`;
                }
              }

              async function runLinkedinAutoProfileAnalysis() {
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx) {
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» para usar a auto-análise.</motion>`;
                  updateLinkedinAuthButtons(false);
                  return;
                }
                captureLinkedinOAuthTokens(ctx.session);
                await runLinkedinProfileAnalysis({ autoAuthenticated: true });
              }

              if (profileInput) {
                profileInput.addEventListener("keydown", (e) => {
                  if (e.key === "Enter") runLinkedinProfileAnalysis();
                });
              }
              if (myProfileInput) {
                myProfileInput.addEventListener("input", updateAutoAnalyzeButton);
              }

              (async function setupLinkedinAuthListener() {
                const sb = await getLinkedinSupabaseClient();
                if (!sb) return;
                sb.auth.onAuthStateChange((event, session) => {
                  if (session) captureLinkedinOAuthTokens(session);
                  if (event === "SIGNED_IN" && session) tryResolveLinkedinProfileUrl(sb);
                  refreshLinkedinSupabaseSession();
                });
              })();

              (async function bootstrapLinkedinPage() {
                await initSupabaseAuthFromUrl();
                applyStoredLinkedinProfileUrl();
                await refreshLinkedinSupabaseSession();
              })();
            </script>
          </body>
        </html>
"""

TAIL = (
    TAIL.replace("<motion ", "<motion ")
    .replace('class="err"><strong>Erro:</strong> Cola o URL público', 'class="err"><strong>Erro:</strong> Cola o URL público')
    .replace(
        'result.innerHTML = `<motion class="err"><strong>Erro:</strong> Cola o URL público em «Analisar outro perfil».</motion>`;',
        'result.innerHTML = `<div class="err"><strong>Erro:</strong> Cola o URL público em «Analisar outro perfil».</div>`;',
    )
    .replace(
        'result.innerHTML = `<div class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» para usar a auto-análise.</motion>`;',
        'result.innerHTML = `<motion class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» para usar a auto-análise.</div>`;',
    )
)
# Fix motion tags introduced above
TAIL = TAIL.replace("<motion ", "<div ").replace("</motion>", "</div>")
TAIL = TAIL.replace('data-target="evolution">Plano &amp; Ações</div>', 'data-target="evolution">Plano &amp; Ações</div>')

h = h + TAIL
h = h.replace("<motion ", "<div ").replace("</motion>", "</div>")
h = h.replace('<motion class="spinner"></div>', '<div class="spinner"></div>')
h = h.replace('<div class="spinner"></motion>', '<div class="spinner"></motion>'.replace("</motion>", "</div>"))

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")

checks = {
    "run": "async function runLinkedinProfileAnalysis" in h,
    "insights": "principais_insights" in h,
    "metrics_ctx": "renderLinkedinMetricCards(data.metricas_universais, data)" in h,
    "html_close": h.rstrip().endswith("</html>"),
    "unavailable": "METRIC_UNAVAILABLE_PUBLIC" in h,
}
print("repaired", checks)
