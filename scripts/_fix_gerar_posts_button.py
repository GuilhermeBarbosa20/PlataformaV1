# -*- coding: utf-8 -*-
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

if "function enableGeneratePostsButton" not in h:
    h = h.replace(
        "              function resetLinkedinPostsAfterAnalysis() {",
        """              function enableGeneratePostsButton() {
                const enabled = Boolean(linkedinAnalysisSnapshot);
                const label = linkedinGeneratedPosts.length ? "Gerar novamente" : "Gerar posts";
                ["btnGenerateLinkedinPosts"].forEach((id) => {
                  const btn = document.getElementById(id);
                  if (!btn) return;
                  btn.disabled = !enabled;
                  btn.textContent = label;
                });
                document.querySelectorAll("[data-action=generate-linkedin-posts]").forEach((btn) => {
                  btn.disabled = !enabled;
                  if (!btn.textContent || btn.textContent.includes("Gerar")) btn.textContent = label;
                });
              }

              function resetLinkedinPostsAfterAnalysis() {""",
    )

h = h.replace(
    """                const btn = document.getElementById("btnGenerateLinkedinPosts");
                if (btn) {
                  btn.disabled = !linkedinAnalysisSnapshot;
                  btn.textContent = "Gerar posts";
                }""",
    "                enableGeneratePostsButton();",
)

h = h.replace(
    """                  setLinkedinAnalysisSnapshot(data);
                  resetLinkedinPostsAfterAnalysis();

                  const profile = data.public_profile_data || {};""",
    """                  setLinkedinAnalysisSnapshot(data);

                  const profile = data.public_profile_data || {};""",
)

h = h.replace(
    """                  attachTabHandlers();
                  const resolvedUrl = data.profile_url || profile.profile_url || profileValue;""",
    """                  attachTabHandlers();
                  resetLinkedinPostsAfterAnalysis();
                  enableGeneratePostsButton();
                  const resolvedUrl = data.profile_url || profile.profile_url || profileValue;""",
)

if "formatLinkedinAudienceCount" not in h:
    h = h.replace(
        """              function formatPct(value) {
                if (value === null || value === undefined) return "—";
                const num = Number(value);
                if (Number.isNaN(num)) return "—";
                return num.toFixed(2) + "%";
              }""",
        """              function formatPct(value) {
                if (value === null || value === undefined) return "—";
                const num = Number(value);
                if (Number.isNaN(num)) return "—";
                return num.toFixed(2) + "%";
              }

              function formatLinkedinAudienceCount(count) {
                if (count === null || count === undefined || count === "") {
                  return "Dado não público no LinkedIn";
                }
                const n = Number(count);
                if (Number.isNaN(n)) return String(count);
                return formatNumber(n);
              }""",
    )
    h = h.replace(
        "value: formatNumber(profile.followers_count), sub: profile.employer",
        "value: formatLinkedinAudienceCount(profile.followers_count), sub: profile.employer",
    )

BANNER_OLD = """                          ${renderLinkedinMetricCards(data.metricas_universais, data)}
                        </motion>
                      </div>
                    </div>

                    <div id="panel-actions\""""
# try without motion
if BANNER_OLD not in h:
    BANNER_OLD = """                          ${renderLinkedinMetricCards(data.metricas_universais, data)}
                        </div>
                      </div>
                    </div>

                    <div id="panel-actions\""""

if "li-posts-cta-banner" not in h and BANNER_OLD in h:
    BANNER_NEW = """                          ${renderLinkedinMetricCards(data.metricas_universais, data)}
                        </div>
                      </div>
                      <motion class="section li-posts-cta-banner">
                        <h3>Posts com IA <span class="pill violet">publicar</span></h3>
                        <p class="section-desc">Gera rascunhos a partir desta análise. Na aba <strong>Plano &amp; Ações</strong> podes aprovar, editar e refazer cada post.</p>
                        <button type="button" class="btn-analyze" style="margin-top:8px;max-width:260px" data-action="generate-linkedin-posts" onclick="generateLinkedinPostsFromSnapshot()">Gerar posts</button>
                      </div>
                    </div>

                    <div id="panel-actions\""""
    BANNER_NEW = BANNER_NEW.replace('<motion class="section', '<div class="section').replace("</motion>\n                      </div>", "</div>\n                      </div>")
    h = h.replace(BANNER_OLD, BANNER_NEW, 1)

if ".li-posts-cta-banner" not in h:
    h = h.replace(
        ".li-metrics-section { margin-top: 4px; }",
        ".li-posts-cta-banner { border-color: rgba(129,140,248,0.35); background: rgba(129,140,248,0.06); }\n              .li-metrics-section { margin-top: 4px; }",
    )

h = h.replace(
    'id="btnGenerateLinkedinPosts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>',
    'id="btnGenerateLinkedinPosts" data-action="generate-linkedin-posts" onclick="generateLinkedinPostsFromSnapshot()" disabled>Gerar posts</button>',
)

if "enableGeneratePostsButton();" not in h.split("generateLinkedinPostsFromSnapshot")[1][:1500]:
    h = h.replace(
        "                  renderLinkedinPostsContainer();\n                } catch (e) {",
        "                  renderLinkedinPostsContainer();\n                  enableGeneratePostsButton();\n                } catch (e) {",
        1,
    )

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print(
    "ok",
    {
        "enable": "enableGeneratePostsButton" in h,
        "order": "attachTabHandlers();\n                  resetLinkedinPostsAfterAnalysis();" in h,
        "banner": "li-posts-cta-banner" in h,
        "audience": "formatLinkedinAudienceCount" in h,
    },
)
