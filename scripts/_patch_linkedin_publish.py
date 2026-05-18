# -*- coding: utf-8 -*-
"""Botões publicar no LinkedIn (texto + imagem ou só texto)."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"

raw = PAGE.read_text(encoding="utf-8")
_, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

PUBLISH_CSS = """
              .li-post-publish-section {
                margin-top: 14px; padding-top: 12px;
                border-top: 1px solid var(--line-strong);
              }
              .li-post-publish-label {
                font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
                letter-spacing: 0.06em; color: var(--muted-soft); margin-bottom: 8px;
              }
              .li-post-publish-actions { display: flex; flex-wrap: wrap; gap: 8px; }
              .li-post-publish-actions button {
                padding: 8px 14px; font-size: 0.84rem; border-radius: 8px; font-weight: 600;
              }
              .btn-post-publish {
                background: linear-gradient(135deg, #0a66c2, #004182);
                border: 1px solid rgba(10,102,194,0.5); color: #fff;
              }
              .btn-post-publish:hover { filter: brightness(1.08); }
              .btn-post-publish.secondary {
                background: rgba(10,102,194,0.12); color: #7eb8f7;
                border: 1px solid rgba(10,102,194,0.35);
              }
              .li-post-published-msg {
                font-size: 0.85rem; color: var(--good); font-weight: 600;
              }
              .li-post-publish-loading { font-size: 0.85rem; color: var(--accent); }
"""

if ".li-post-publish-section" not in h:
    h = h.replace(
        ".li-post-card.image-approved .li-post-image-section {",
        PUBLISH_CSS + "\n              .li-post-card.image-approved .li-post-image-section {",
    )

anchor = 'const cardCls = [cls, imgSt === "approved"'
if anchor not in h:
    raise SystemExit("cardCls anchor not found")

PUBLISH_BLOCK_JS = """                  let publishBlock = "";
                  if (p.publishing_linkedin) {
                    publishBlock = '<motion class="li-post-publish-loading">A publicar no LinkedIn…</motion>';
                  } else if (p.published_on_linkedin) {
                    publishBlock = '<div class="li-post-publish-section"><div class="li-post-published-msg">Publicado no LinkedIn</div></div>';
                  } else if (st === "approved") {
                    const canPublishImage = p.image_status === "approved" && p.generated_image_url;
                    if (canPublishImage) {
                      publishBlock = `
                        <div class="li-post-publish-section">
                          <div class="li-post-publish-label">Publicar no LinkedIn</div>
                          <div class="li-post-publish-actions">
                            <button type="button" class="btn-post-publish" onclick="publishLinkedinPost('${escapeHtml(p.id)}', true)">Publicar texto + imagem</button>
                            <button type="button" class="btn-post-publish secondary" onclick="publishLinkedinPost('${escapeHtml(p.id)}', false)">Publicar só texto</button>
                          </div>
                        </div>`;
                    } else {
                      publishBlock = `
                        <div class="li-post-publish-section">
                          <div class="li-post-publish-label">Publicar no LinkedIn</motion>
                          <div class="li-post-publish-actions">
                            <button type="button" class="btn-post-publish" onclick="publishLinkedinPost('${escapeHtml(p.id)}', false)">Publicar no LinkedIn</button>
                          </div>
                        </div>`;
                    }
                  }
                  """
PUBLISH_BLOCK_JS = (
    PUBLISH_BLOCK_JS.replace(
        "publishBlock = '<motion class=\"li-post-publish-loading\">A publicar no LinkedIn…</motion>';",
        "publishBlock = '<div class=\"li-post-publish-loading\">A publicar no LinkedIn…</div>';",
    ).replace(
        '<div class="li-post-publish-label">Publicar no LinkedIn</motion>',
        '<div class="li-post-publish-label">Publicar no LinkedIn</div>',
    )
)

if "let publishBlock" not in h:
    h = h.replace(anchor, PUBLISH_BLOCK_JS + anchor)

if "${publishBlock}" not in h:
    marker = '<motion class="li-post-actions">${actions}</motion>'
    marker = marker.replace("<motion", "<div").replace("</motion>", "</div>")
    if marker not in h:
        marker = '<div class="li-post-actions">${actions}</div>'
    if marker not in h:
        raise SystemExit("li-post-actions marker not found")
    h = h.replace(
        marker,
        "${publishBlock}\n                      " + marker,
        1,
    )

PUBLISH_FN = """
              async function publishLinkedinPost(id, includeImage) {
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p || p.status !== "approved" || p.published_on_linkedin) return;
                if (includeImage && (!p.generated_image_url || p.image_status !== "approved")) {
                  alert("Aprova a imagem antes de publicar com imagem.");
                  return;
                }
                const modeLabel = includeImage ? "texto + imagem" : "só texto";
                if (!confirm("Publicar no LinkedIn (" + modeLabel + ")?\\n\\nSerá usada a conta com que fizeste login.")) return;
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx || !ctx.session) {
                  alert("Inicia sessão com LinkedIn para publicar.");
                  return;
                }
                const payload = appendLinkedinSessionFields({
                  include_image: !!includeImage,
                  post: {
                    id: p.id,
                    title: p.title,
                    body: p.body,
                    hook: p.hook,
                    cta: p.cta,
                    content_type: p.content_type,
                    generated_image_url: p.generated_image_url || null,
                    status: p.status,
                    image_status: p.image_status || null,
                  },
                }, ctx.session);
                p.publishing_linkedin = true;
                renderLinkedinPostsContainer();
                try {
                  const resp = await fetch("/agents/linkedin/publish-post", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                  });
                  const data = await resp.json().catch(() => ({}));
                  if (!resp.ok) {
                    const msg = data.detail || data.error || "Falha ao publicar.";
                    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
                  }
                  p.published_on_linkedin = true;
                  p.linkedin_post_urn = data.linkedin_post_urn || "";
                  p.published_with_image = !!data.published_with_image;
                } catch (err) {
                  alert(err && err.message ? err.message : "Não foi possível publicar no LinkedIn.");
                } finally {
                  p.publishing_linkedin = false;
                  renderLinkedinPostsContainer();
                }
              }

"""

if "async function publishLinkedinPost" not in h:
    insert_at = h.find("async function regenerateLinkedinPostImage")
    if insert_at < 0:
        raise SystemExit("insert point not found")
    h = h[:insert_at] + PUBLISH_FN + h[insert_at:]

OLD_DEL = "delete p.image_status;"
NEW_DEL = (
    "delete p.image_status;\n"
    "                  delete p.published_on_linkedin;\n"
    "                  delete p.linkedin_post_urn;\n"
    "                  delete p.published_with_image;\n"
    "                  delete p.publishing_linkedin;"
)
if OLD_DEL in h and "delete p.published_on_linkedin" not in h:
    h = h.replace(OLD_DEL, NEW_DEL)

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
print("ok", "publishLinkedinPost" in h, "${publishBlock}" in h)
