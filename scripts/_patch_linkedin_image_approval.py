# -*- coding: utf-8 -*-
"""Aprovar / refazer imagem do post LinkedIn (mesmo esquema que o texto)."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"

raw = PAGE.read_text(encoding="utf-8")
_, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

EXTRA_CSS = """
              .li-post-image-section {
                margin: 12px 0 4px; padding-top: 12px;
                border-top: 1px dashed var(--line);
              }
              .li-post-image-head {
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 8px; gap: 8px;
              }
              .li-post-image-label {
                font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
                letter-spacing: 0.06em; color: var(--muted-soft);
              }
              .li-post-image-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
              .li-post-image-actions button {
                padding: 7px 12px; font-size: 0.82rem; border-radius: 8px;
              }
              .li-post-card.image-approved .li-post-image-section {
                border-top-color: rgba(52,211,153,0.35);
              }
"""

if ".li-post-image-section" not in h:
    anchor = ".li-post-image-loading {\n                font-size: 0.85rem; color: var(--accent); margin: 8px 0 10px;\n              }"
    if anchor not in h:
        raise SystemExit("CSS anchor not found")
    h = h.replace(anchor, anchor + EXTRA_CSS)

# Locate imageBlock block dynamically
start = h.find("const imageBlock = p.image_generating")
end = h.find("return `", start)
if start < 0 or end < 0:
    if "approveLinkedinPostImage" in h:
        print("image UI já patchada")
    else:
        raise SystemExit("imageBlock start not found")
else:
    NEW_IMAGE_BLOCK = r"""const imgSt = p.image_status || "draft";
                  let imageBlock = "";
                  if (p.image_generating) {
                    imageBlock = '<motion class="li-post-image-loading">A gerar imagem…</motion>';
                  } else if (p.generated_image_url) {
                    const imgStatusLabel = imgSt === "approved"
                      ? '<span class="li-post-status ok">Imagem aprovada</span>'
                      : '<span class="li-post-status">Imagem em rascunho</span>';
                    const imgActions = imgSt === "approved"
                      ? `<button type="button" class="btn-post-ok" disabled>Aprovado</button>`
                      : `<button type="button" class="btn-post-ok" onclick="approveLinkedinPostImage('${escapeHtml(p.id)}')">Aprovado</button>
                         <button type="button" class="btn-post-redo" onclick="regenerateLinkedinPostImage('${escapeHtml(p.id)}')">Refazer</button>`;
                    imageBlock = `
                      <div class="li-post-image-section">
                        <div class="li-post-image-head">
                          <span class="li-post-image-label">Imagem</span>
                          ${imgStatusLabel}
                        </div>
                        <div class="li-post-image-wrap">
                          <img src="${escapeHtml(p.generated_image_url)}" alt="Imagem do post" class="li-post-image" />
                          <a class="li-post-image-link" href="${escapeHtml(p.generated_image_url)}" target="_blank" rel="noopener noreferrer">Abrir imagem</a>
                        </div>
                        <div class="li-post-image-actions">${imgActions}</div>
                      </motion>`;
                  }
                  const cardCls = [cls, imgSt === "approved" && p.generated_image_url ? "image-approved" : ""].filter(Boolean).join(" ");
                  """
    NEW_IMAGE_BLOCK = (
        NEW_IMAGE_BLOCK.replace("<motion class=", "<motion class=")
        .replace("</motion>`;", "</motion>`;")
        .replace("'<motion class=\"li-post-image-loading\">A gerar imagem…</motion>'", "'<div class=\"li-post-image-loading\">A gerar imagem…</div>'")
        .replace("<motion class=\"li-post-image-loading\">", "<div class=\"li-post-image-loading\">")
        .replace("                      </motion>`;", "                      </motion>`;")
    )
    # fix botched replace - do clean version
    NEW_IMAGE_BLOCK = """const imgSt = p.image_status || "draft";
                  let imageBlock = "";
                  if (p.image_generating) {
                    imageBlock = '<div class="li-post-image-loading">A gerar imagem…</div>';
                  } else if (p.generated_image_url) {
                    const imgStatusLabel = imgSt === "approved"
                      ? '<span class="li-post-status ok">Imagem aprovada</span>'
                      : '<span class="li-post-status">Imagem em rascunho</span>';
                    const imgActions = imgSt === "approved"
                      ? `<button type="button" class="btn-post-ok" disabled>Aprovado</button>`
                      : `<button type="button" class="btn-post-ok" onclick="approveLinkedinPostImage('${escapeHtml(p.id)}')">Aprovado</button>
                         <button type="button" class="btn-post-redo" onclick="regenerateLinkedinPostImage('${escapeHtml(p.id)}')">Refazer</button>`;
                    imageBlock = `
                      <div class="li-post-image-section">
                        <div class="li-post-image-head">
                          <span class="li-post-image-label">Imagem</span>
                          ${imgStatusLabel}
                        </div>
                        <motion class="li-post-image-wrap">
                          <img src="${escapeHtml(p.generated_image_url)}" alt="Imagem do post" class="li-post-image" />
                          <a class="li-post-image-link" href="${escapeHtml(p.generated_image_url)}" target="_blank" rel="noopener noreferrer">Abrir imagem</a>
                        </div>
                        <div class="li-post-image-actions">${imgActions}</div>
                      </div>`;
                  }
                  const cardCls = [cls, imgSt === "approved" && p.generated_image_url ? "image-approved" : ""].filter(Boolean).join(" ");
                  """
    NEW_IMAGE_BLOCK = NEW_IMAGE_BLOCK.replace(
        '<motion class="li-post-image-wrap">',
        '<div class="li-post-image-wrap">',
    )
    h = h[:start] + NEW_IMAGE_BLOCK + h[end:]

if '<motion class="${cls}"' in h or '<div class="${cls}"' in h:
    h = h.replace(
        '<div class="${cls}" data-post-id="${escapeHtml(p.id)}">',
        '<div class="${cardCls}" data-post-id="${escapeHtml(p.id)}">',
        1,
    )

OLD_APPROVE_TAIL = """                p.image_generating = true;
                renderLinkedinPostsContainer();
                try {
                  const resp = await fetch("/agents/linkedin/generate-post-image", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      post: {
                        id: p.id,
                        title: p.title,
                        body: p.body,
                        hook: p.hook,
                        cta: p.cta,
                        content_type: p.content_type,
                      },
                    }),
                  });
                  const data = await resp.json().catch(() => ({}));
                  if (!resp.ok) {
                    const msg = data.detail || data.error || "Falha ao gerar imagem.";
                    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
                  }
                  p.generated_image_url = data.image_url || "";
                  p.generated_image_prompt = data.prompt_used || "";
                } catch (err) {
                  alert(err && err.message ? err.message : "Não foi possível gerar a imagem.");
                } finally {
                  p.image_generating = false;
                  renderLinkedinPostsContainer();
                }
              }"""

NEW_HELPERS = """                await linkedinGeneratePostImage(p, null);
              }

              async function linkedinGeneratePostImage(p, editInstructions) {
                if (!p) return;
                p.image_generating = true;
                p.image_status = "draft";
                renderLinkedinPostsContainer();
                try {
                  const resp = await fetch("/agents/linkedin/generate-post-image", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      post: {
                        id: p.id,
                        title: p.title,
                        body: p.body,
                        hook: p.hook,
                        cta: p.cta,
                        content_type: p.content_type,
                      },
                      edit_instructions: editInstructions || null,
                    }),
                  });
                  const data = await resp.json().catch(() => ({}));
                  if (!resp.ok) {
                    const msg = data.detail || data.error || "Falha ao gerar imagem.";
                    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
                  }
                  p.generated_image_url = data.image_url || "";
                  p.generated_image_prompt = data.prompt_used || "";
                  p.image_status = "draft";
                } catch (err) {
                  alert(err && err.message ? err.message : "Não foi possível gerar a imagem.");
                } finally {
                  p.image_generating = false;
                  renderLinkedinPostsContainer();
                }
              }

              function approveLinkedinPostImage(id) {
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p || !p.generated_image_url || p.image_status === "approved") return;
                p.image_status = "approved";
                renderLinkedinPostsContainer();
              }

              async function regenerateLinkedinPostImage(id) {
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p || !p.generated_image_url) return;
                const instr = window.prompt("Instruções para refazer a imagem (opcional):", "") || "";
                await linkedinGeneratePostImage(p, instr || null);
              }"""

if OLD_APPROVE_TAIL in h:
    h = h.replace(OLD_APPROVE_TAIL, NEW_HELPERS)
elif "linkedinGeneratePostImage" not in h:
    raise SystemExit("approveLinkedinPost tail not found")

OLD_REGEN_DELETE = (
    "                  delete p.generated_image_url;\n"
    "                  delete p.generated_image_prompt;\n"
    "                  delete p.image_generating;"
)
NEW_REGEN_DELETE = (
    "                  delete p.generated_image_url;\n"
    "                  delete p.generated_image_prompt;\n"
    "                  delete p.image_generating;\n"
    "                  delete p.image_status;"
)
if OLD_REGEN_DELETE in h and "delete p.image_status" not in h:
    h = h.replace(OLD_REGEN_DELETE, NEW_REGEN_DELETE)

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
print("ok", len(h))
