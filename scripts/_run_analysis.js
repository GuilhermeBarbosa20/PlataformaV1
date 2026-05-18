async function runLinkedinProfileAnalysis() {
                const profileValue = profileInput.value.trim();
                const pl = "linkedin";
                let supabaseToken = null;
                let linkedinProviderToken = null;
                let useSessionProfile = false;

                if (SUPABASE_PUBLIC_URL && SUPABASE_ANON_KEY) {
                  try {
                    const sb = await getLinkedinSupabaseClient();
                    if (!sb) throw new Error("no client");
                    const { data } = await sb.auth.getSession();
                    if (data.session && data.session.access_token) {
                      supabaseToken = data.session.access_token;
                      linkedinProviderToken = data.session.provider_token || null;
                      if (!profileValue) useSessionProfile = true;
                    }
                  } catch (e) {
                    /* segue sem sessão */
                  }
                }

                if (!useSessionProfile && !profileValue) {
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> Inicia sessão com «Login LinkedIn (Supabase)» ou cola o URL público do perfil.</div>`;
                  return;
                }

                const endpoint = "/agents/social-media/profile-analyze";
                const payload = {
                  profile_input: profileValue,
                  messages: [],
                  language: "pt-PT",
                  platform: pl,
                };
                if (supabaseToken) {
                  payload.supabase_access_token = supabaseToken;
                }
                if (linkedinProviderToken) {
                  payload.linkedin_provider_token = linkedinProviderToken;
                }
                const loadingHint = useSessionProfile
                  ? "A recolher o teu perfil LinkedIn (sessão + Apify)…"
                  : "LinkedIn (Apify + OpenAI) — pode demorar…";
                result.innerHTML = `
                  <div class="loading">
                    <div class="spinner"></div>
                    <div>
                      <div style="color: var(--text); font-weight:600">A processar análise</div>
                      <div style="font-size:0.85rem">${escapeHtml(loadingHint)}</div>
                    </div>
                  </div>
                `;
                try {
                  const response = await fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    credentials: "same-origin",
                    body: JSON.stringify(payload)
                  });
                  const data = await response.json();
                  if (!response.ok) {
                    const detailText = data.detail || JSON.stringify(data);
                    result.innerHTML = `<div class="err"><strong>Erro:</strong> ${escapeHtml(detailText)}</div>`;
                    return;
                  }

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
                      <div class="section">
                        <h3>Performance (LinkedIn) <span class="pill cool">métricas</span></h3>
                        ${renderMetricPills(data.metricas_universais)}
                      </div>
                      <div class="section">
                        <h3>Métricas específicas (${escapeHtml(data.plataforma_label || "LinkedIn")})</h3>
                        ${renderMetricPills(data.metricas_linkedin || data.metricas_instagram)}
                      </div>
                    </div>

                    <div id="panel-actions" class="panel">
                      <div class="section">
                        <h3>Ações Prioritárias <span class="pill">agora</span></h3>
                        <ul class="insight-list actions">${listSection(data.acoes_prioritarias)}</ul>
                      </div>
                      <div class="section">
                        <h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>
                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>
                      </div>
                      <div class="section">
                        <h3>Plano de Crescimento (curto prazo)</h3>
                        <ul class="insight-list">${listSection(data.plano_crescimento_curto_prazo)}</ul>
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
                        <h3>Destaques <span class="pill violet">posts</span></h3>
                        ${renderTopCards(enrichment.top_posts, "publicações")}
                      </div>
                      <div class="section">
                        <h3>Cadência de publicação</h3>
                        ${renderCadence(enrichment.posting_cadence || {}, {})}
                      </div>

                    </div>

                    <div id="panel-evolution" class="panel">
                      <div class="section">
                        <h3>Comparação Temporal</h3>
                        ${renderComparisons(data.comparisons)}
                      </div>
                      <div class="section">
                        <h3>Lacunas de Dados</h3>
                        <ul class="gap-list">${listSection(data.lacunas_de_dados)}</ul>
                      </div>
                    </div>
                  `;
                  attachTabHandlers();
                                  } catch (err) {
                  const errorMessage = err instanceof Error ? err.message : String(err);
                  result.innerHTML = `<div class="err"><strong>Erro:</strong> ${escapeHtml(errorMessage)}</div>`;
                }
              }

              