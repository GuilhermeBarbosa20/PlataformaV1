# -*- coding: utf-8 -*-
"""Após aprovar post LinkedIn, pergunta se gera imagem e mostra preview."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"

raw = PAGE.read_text(encoding="utf-8")
head, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

IMAGE_CSS = """
              .li-post-image-wrap { margin: 10px 0 12px; }
              .li-post-image {
                max-width: 100%; max-height: 420px; width: auto; height: auto;
                border-radius: 10px; border: 1px solid var(--line);
                display: block; object-fit: contain;
              }
              .li-post-image-link {
                display: inline-block; margin-top: 6px; font-size: 0.78rem;
                color: var(--accent); text-decoration: none;
              }
              .li-post-image-link:hover { text-decoration: underline; }
              .li-post-image-loading {
                font-size: 0.85rem; color: var(--accent); margin: 8px 0 10px;
              }
"""

if ".li-post-image-wrap" not in h:
    h = h.replace(
        ".li-posts-loading { color: var(--muted); font-size: 0.88rem; padding: 12px 0; }",
        ".li-posts-loading { color: var(--muted); font-size: 0.88rem; padding: 12px 0; }"
        + IMAGE_CSS,
    )

OLD_APPROVE = """              function approveLinkedinPost(id) {
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p) return;
                p.status = "approved";
                renderLinkedinPostsContainer();
              }"""

NEW_APPROVE = """              async function approveLinkedinPost(id) {
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p || p.status === "approved") return;
                p.status = "approved";
                renderLinkedinPostsContainer();
                const wantImage = confirm(
                  "Queres gerar uma imagem para este post?\\n\\n" +
                  "OK — gera uma imagem alinhada ao texto.\\n" +
                  "Cancelar — mantém só o texto aprovado."
                );
                if (!wantImage) return;
                p.image_generating = true;
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

if OLD_APPROVE not in h:
    if "async function approveLinkedinPost" in h:
        print("approveLinkedinPost já actualizado")
    else:
        raise SystemExit("approveLinkedinPost anchor not found")
else:
    h = h.replace(OLD_APPROVE, NEW_APPROVE)

OLD_ACTIONS_BLOCK = """                    : `<button type="button" class="btn-post-ok" onclick="approveLinkedinPost('${escapeHtml(p.id)}')" ${st === "approved" ? "disabled" : ""}>Aprovado</button>
                       <button type="button" class="btn-post-edit" onclick="startLinkedinPostEdit('${escapeHtml(p.id)}')">Editar</button>
                       <button type="button" class="btn-post-redo" onclick="regenerateLinkedinPost('${escapeHtml(p.id)}')">Refazer</button>`;
                  return `"""

NEW_ACTIONS_BLOCK = """                    : `<button type="button" class="btn-post-ok" onclick="approveLinkedinPost('${escapeHtml(p.id)}')" ${st === "approved" ? "disabled" : ""}>Aprovado</button>
                       <button type="button" class="btn-post-edit" onclick="startLinkedinPostEdit('${escapeHtml(p.id)}')">Editar</button>
                       <button type="button" class="btn-post-redo" onclick="regenerateLinkedinPost('${escapeHtml(p.id)}')">Refazer</button>`;
                  const imageBlock = p.image_generating
                    ? '<div class="li-post-image-loading">A gerar imagem…</div>'
                    : (p.generated_image_url
                      ? `<div class="li-post-image-wrap"><img src="${escapeHtml(p.generated_image_url)}" alt="Imagem do post" class="li-post-image" /><a class="li-post-image-link" href="${escapeHtml(p.generated_image_url)}" target="_blank" rel="noopener noreferrer">Abrir imagem</a></div>`
                      : "");
                  return `"""

if "const imageBlock = p.image_generating" not in h:
    if OLD_ACTIONS_BLOCK not in h:
        raise SystemExit("actions block anchor not found")
    h = h.replace(OLD_ACTIONS_BLOCK, NEW_ACTIONS_BLOCK)

# insert imageBlock in template - find angle line dynamically
angle_idx = h.find("${p.angle ?")
if angle_idx < 0:
    raise SystemExit("p.angle anchor not found")

# find start of line with p.cta before angle
cta_line_start = h.rfind("${p.cta ?", 0, angle_idx)
if cta_line_start < 0:
    raise SystemExit("p.cta anchor not found")

# After cta block line(s), we need hook+cta+angle - insert imageBlock before angle
# Safer: insert before ${p.angle
if "${imageBlock}" not in h:
    h = h.replace(
        "${p.angle ?",
        "${imageBlock}\n                      ${p.angle ?",
        1,
    )

OLD_REGEN_ASSIGN = "Object.assign(p, updated, { id: p.id, status: \"draft\" });\n                  delete p.bodyEdit;"
NEW_REGEN_ASSIGN = (
    "Object.assign(p, updated, { id: p.id, status: \"draft\" });\n"
    "                  delete p.bodyEdit;\n"
    "                  delete p.generated_image_url;\n"
    "                  delete p.generated_image_prompt;\n"
    "                  delete p.image_generating;"
)

if OLD_REGEN_ASSIGN in h and "delete p.generated_image_url" not in h:
    h = h.replace(OLD_REGEN_ASSIGN, NEW_REGEN_ASSIGN)

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
print("linkedin_perfil_page.py updated", len(h))
