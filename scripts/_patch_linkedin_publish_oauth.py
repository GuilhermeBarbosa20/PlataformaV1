# -*- coding: utf-8 -*-
"""OAuth dedicado w_member_social + botão Autorizar publicação."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
_, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

if "LINKEDIN_PUBLISH_TOKEN_KEY" not in h:
    h = h.replace(
        'const LINKEDIN_PROVIDER_TOKEN_KEY = "plataforma_linkedin_provider_token";',
        'const LINKEDIN_PROVIDER_TOKEN_KEY = "plataforma_linkedin_provider_token";\n'
        '              const LINKEDIN_PUBLISH_TOKEN_KEY = "plataforma_linkedin_publish_token";\n'
        '              const LINKEDIN_PUBLISH_URN_KEY = "plataforma_linkedin_publish_person_urn";\n'
        '              const LINKEDIN_PUBLISH_EXPIRES_KEY = "plataforma_linkedin_publish_expires_at";',
    )

HELPERS = """
              function getPersistedLinkedinPublishToken() {
                try {
                  const exp = Number(sessionStorage.getItem(LINKEDIN_PUBLISH_EXPIRES_KEY) || 0);
                  if (exp && Date.now() > exp) {
                    sessionStorage.removeItem(LINKEDIN_PUBLISH_TOKEN_KEY);
                    sessionStorage.removeItem(LINKEDIN_PUBLISH_URN_KEY);
                    sessionStorage.removeItem(LINKEDIN_PUBLISH_EXPIRES_KEY);
                    return null;
                  }
                  return sessionStorage.getItem(LINKEDIN_PUBLISH_TOKEN_KEY) || null;
                } catch (e) {
                  return null;
                }
              }

              function hasLinkedinPublishAuthorization() {
                return Boolean(getPersistedLinkedinPublishToken());
              }

              function connectLinkedinPublish() {
                window.location.href = "/agents/linkedin/connect-publish";
              }

              (function handlePublishOAuthReturn() {
                try {
                  const q = new URLSearchParams(window.location.search);
                  if (q.get("publish_connected") === "1") {
                    history.replaceState({}, "", window.location.pathname);
                  }
                } catch (e) {}
              })();

"""

if "function getPersistedLinkedinPublishToken" not in h:
    ins = h.find("async function publishLinkedinPost")
    h = h[:ins] + HELPERS + h[ins:]

OLD_PAYLOAD = """                const payload = appendLinkedinSessionFields({
                  include_image: !!includeImage,
                  post: {"""

NEW_PAYLOAD = """                const publishTok = getPersistedLinkedinPublishToken();
                if (!publishTok) {
                  alert("Primeiro clica em «Autorizar publicação no LinkedIn» na secção Publicar.");
                  return;
                }
                const payload = appendLinkedinSessionFields({
                  include_image: !!includeImage,
                  linkedin_publish_access_token: publishTok,
                  post: {"""

if OLD_PAYLOAD in h and "linkedin_publish_access_token" not in h:
    h = h.replace(OLD_PAYLOAD, NEW_PAYLOAD)

OLD_BLOCK_START = "let publishBlock = \"\";"
OLD_BLOCK_END = "const cardCls = [cls, imgSt === \"approved\""

i0 = h.find(OLD_BLOCK_START)
i1 = h.find(OLD_BLOCK_END)
if i0 < 0 or i1 < 0:
    raise SystemExit("publishBlock anchors not found")

NEW_BLOCK = r'''let publishBlock = "";
                  const publishAuthOk = hasLinkedinPublishAuthorization();
                  const publishAuthBtn = publishAuthOk
                    ? '<span class="li-post-status ok" style="margin-left:8px">Publicação autorizada</span>'
                    : '<button type="button" class="btn-post-publish secondary" onclick="connectLinkedinPublish()">Autorizar publicação no LinkedIn</button>';
                  if (p.publishing_linkedin) {
                    publishBlock = '<div class="li-post-publish-loading">A publicar no LinkedIn…</div>';
                  } else if (p.published_on_linkedin) {
                    publishBlock = '<div class="li-post-publish-section"><div class="li-post-published-msg">Publicado no LinkedIn</div></div>';
                  } else if (st === "approved") {
                    const canPublishImage = p.image_status === "approved" && p.generated_image_url;
                    const pubDisabled = publishAuthOk ? "" : " disabled";
                    if (canPublishImage) {
                      publishBlock = `
                        <div class="li-post-publish-section">
                          <div class="li-post-publish-label">Publicar no LinkedIn ${publishAuthBtn}</div>
                          <p style="font-size:0.78rem;color:var(--muted);margin:0 0 8px">O login Supabase analisa o perfil; autoriza aqui para publicar posts.</p>
                          <div class="li-post-publish-actions">
                            <button type="button" class="btn-post-publish" onclick="publishLinkedinPost('${escapeHtml(p.id)}', true)"${pubDisabled}>Publicar texto + imagem</button>
                            <button type="button" class="btn-post-publish secondary" onclick="publishLinkedinPost('${escapeHtml(p.id)}', false)"${pubDisabled}>Publicar só texto</button>
                          </div>
                        </div>`;
                    } else {
                      publishBlock = `
                        <div class="li-post-publish-section">
                          <div class="li-post-publish-label">Publicar no LinkedIn ${publishAuthBtn}</div>
                          <p style="font-size:0.78rem;color:var(--muted);margin:0 0 8px">O login Supabase analisa o perfil; autoriza aqui para publicar posts.</p>
                          <div class="li-post-publish-actions">
                            <button type="button" class="btn-post-publish" onclick="publishLinkedinPost('${escapeHtml(p.id)}', false)"${pubDisabled}>Publicar no LinkedIn</button>
                          </div>
                        </div>`;
                    }
                  }
                  '''

NEW_BLOCK = (
    NEW_BLOCK.replace("<motion", "<div")
    .replace("</motion>", "</motion>")
    .replace("A publicar no LinkedIn…</motion>'", "A publicar no LinkedIn…</div>'")
    .replace("                          </motion>\n                        </div>`", "                          </div>\n                        </motion>`")
)
NEW_BLOCK = NEW_BLOCK.replace("</motion>\n                        </motion>`", "</div>\n                        </div>`")
NEW_BLOCK = NEW_BLOCK.replace("A publicar no LinkedIn…</motion>'", "A publicar no LinkedIn…</div>'")

if "hasLinkedinPublishAuthorization" not in h[i0:i1]:
    h = h[:i0] + NEW_BLOCK + h[i1:]

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
print("ok", "connectLinkedinPublish" in h, "linkedin_publish_access_token" in h)
