# -*- coding: utf-8 -*-
"""Posts LinkedIn gerados: aprovar, editar, refazer."""

from __future__ import annotations

import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

POSTS_CSS = """
              .li-posts-wrap { display: grid; gap: 12px; margin-top: 8px; }
              .li-post-card {
                border: 1px solid var(--line);
                border-radius: 14px;
                background: rgba(255,255,255,0.02);
                padding: 14px 16px;
                transition: border-color 0.15s;
              }
              .li-post-card.approved { border-color: rgba(52,211,153,0.45); background: rgba(52,211,153,0.06); }
              .li-post-card.editing { border-color: rgba(56,189,248,0.45); }
              .li-post-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 8px; }
              .li-post-type {
                font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
                letter-spacing: 0.06em; color: var(--accent-2);
                background: rgba(129,140,248,0.12); padding: 3px 8px; border-radius: 999px;
              }
              .li-post-status { font-size: 0.78rem; color: var(--muted); }
              .li-post-status.ok { color: var(--good); font-weight: 600; }
              .li-post-title { font-weight: 700; margin: 0 0 6px; font-size: 0.95rem; }
              .li-post-body {
                white-space: pre-wrap; font-size: 0.9rem; line-height: 1.55;
                color: var(--muted-soft); margin: 0 0 8px;
              }
              .li-post-meta { font-size: 0.78rem; color: var(--muted); margin-bottom: 10px; }
              .li-post-actions { display: flex; flex-wrap: wrap; gap: 8px; }
              .li-post-actions button {
                padding: 7px 12px; font-size: 0.82rem; border-radius: 8px;
              }
              .btn-post-ok { background: rgba(52,211,153,0.15); border: 1px solid rgba(52,211,153,0.35); color: var(--good); }
              .btn-post-edit { background: rgba(56,189,248,0.12); border: 1px solid rgba(56,189,248,0.3); color: var(--accent); }
              .btn-post-redo { background: rgba(255,61,127,0.12); border: 1px solid rgba(255,61,127,0.3); color: var(--primary); }
              .btn-post-del { background: transparent; border: 1px solid var(--line); color: var(--muted-soft); }
              .li-post-edit-area {
                width: 100%; min-height: 140px; margin: 8px 0 10px;
                border-radius: 10px; border: 1px solid var(--line);
                background: rgba(8,9,13,0.5); color: var(--text);
                padding: 10px 12px; font-family: inherit; font-size: 0.9rem;
                line-height: 1.5; resize: vertical;
              }
              .li-posts-loading { color: var(--muted); font-size: 0.88rem; padding: 12px 0; }
"""

if ".li-post-card" not in h:
    h = h.replace("@media (max-width: 680px) {", POSTS_CSS + "\n              @media (max-width: 680px) {")

OLD_IDEIAS_SECTION = """                      <div class="section">
                        <h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>
                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>
                      </motion>""".replace("</motion>", "</div>")

OLD_IDEIAS_SECTION = """                      <motion class="section">
                        <h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>
                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>
                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>
                      </motion>""".replace("<motion", "<div").replace("motion>", "div>")

# exact from file
OLD_IDEIAS_SECTION = (
    '                      <div class="section">\n'
    '                        <h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>\n'
    '                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>\n'
    '                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>\n'
    "                      </motion>\n"
).replace("</motion>", "</motion>")

OLD_IDEIAS_SECTION = (
    '                      <motion class="section">\n'
    '                        <h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>\n'
    '                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>\n'
    '                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>\n'
    "                      </motion>\n"
)

NEW_IDEIAS_SECTION = (
    '                      <motion class="section" id="linkedinPostsSection">\n'
    '                        <h3>Posts para publicar <span class="pill violet">LinkedIn</span></h3>\n'
    '                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Gerados com IA a partir do teu perfil e da análise. Aprova, edita ou pede para refazer.</p>\n'
    '                        <div id="linkedinPostsContainer" class="li-posts-wrap">\n'
    '                          <div class="li-posts-loading">Os posts serão gerados após a análise…</motion>\n'
    "                        </motion>\n"
    '                        <button type="button" class="btn-save-profile" style="margin-top:10px" onclick="generateLinkedinPostsFromSnapshot()">Gerar novamente</button>\n'
    "                      </motion>\n"
).replace("<motion", "<div").replace("motion>", "div>")

if OLD_IDEIAS_SECTION.replace("<div", "<motion") in h:
    pass

if 'Ideias por tipo de conteúdo' in h and 'linkedinPostsContainer' not in h:
    h = h.replace(OLD_IDEIAS_SECTION.replace("<motion", "<div").replace("motion>", "motion>"), NEW_IDEIAS_SECTION)
    if 'linkedinPostsContainer' not in h:
        h = h.replace(
            '                        <ul class="insight-list violet">${listSection(data.ideias_conteudo)}</ul>',
            '                        <motion id="linkedinPostsContainer" class="li-posts-wrap"><div class="li-posts-loading">A gerar posts…</div></motion>\n'
            '                        <button type="button" class="btn-save-profile" style="margin-top:10px" onclick="generateLinkedinPostsFromSnapshot()">Gerar novamente</button>',
        ).replace("<motion", "<motion").replace("motion>", "motion>")
        h = h.replace(
            '<h3>Ideias por tipo de conteúdo <span class="pill violet">LinkedIn</span></h3>\n'
            '                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Formatos: post texto, artigo, documento/PDF, sondagem, vídeo nativo.</p>',
            '<h3>Posts para publicar <span class="pill violet">LinkedIn</span></h3>\n'
            '                        <p style="color:var(--muted);font-size:0.85rem;margin:0 0 10px">Gerados com IA a partir do teu perfil. Aprova, edita ou refaz cada post.</p>',
        )

POSTS_JS = r"""
              let linkedinAnalysisSnapshot = null;
              let linkedinGeneratedPosts = [];

              const LINKEDIN_POST_TYPE_LABELS = {
                texto: "Post texto", artigo: "Artigo", documento: "Documento/PDF",
                poll: "Sondagem", video: "Vídeo", imagem: "Imagem", partilha: "Partilha"
              };

              function setLinkedinAnalysisSnapshot(data) {
                linkedinAnalysisSnapshot = data ? JSON.parse(JSON.stringify(data)) : null;
              }

              function linkedinPostTypeLabel(t) {
                return LINKEDIN_POST_TYPE_LABELS[t] || t || "Post";
              }

              function renderLinkedinPostsContainer() {
                const el = document.getElementById("linkedinPostsContainer");
                if (!el) return;
                if (!linkedinGeneratedPosts.length) {
                  el.innerHTML = '<div class="li-posts-loading">Sem posts. Clica «Gerar novamente».</motion>';
                  return;
                }
                el.innerHTML = linkedinGeneratedPosts.map((p) => {
                  const st = p.status || "draft";
                  const cls = ["li-post-card", st === "approved" ? "approved" : "", st === "editing" ? "editing" : ""].filter(Boolean).join(" ");
                  const statusLabel = st === "approved" ? '<span class="li-post-status ok">Aprovado</span>' : (st === "editing" ? '<span class="li-post-status">A editar</span>' : '<span class="li-post-status">Rascunho</span>');
                  const bodyBlock = st === "editing"
                    ? `<textarea class="li-post-edit-area" id="edit-area-${escapeHtml(p.id)}">${escapeHtml(p.bodyEdit != null ? p.bodyEdit : p.body)}</textarea>`
                    : `<p class="li-post-body">${escapeHtml(p.body)}</p>`;
                  const actions = st === "editing"
                    ? `<button type="button" class="btn-post-ok" onclick="saveLinkedinPostEdit('${escapeHtml(p.id)}')">Guardar</button>
                       <button type="button" class="btn-post-edit" onclick="cancelLinkedinPostEdit('${escapeHtml(p.id)}')">Cancelar</button>
                       <button type="button" class="btn-post-del" onclick="deleteLinkedinPost('${escapeHtml(p.id)}')">Apagar</button>`
                    : `<button type="button" class="btn-post-ok" onclick="approveLinkedinPost('${escapeHtml(p.id)}')" ${st === "approved" ? "disabled" : ""}>Aprovado</button>
                       <button type="button" class="btn-post-edit" onclick="startLinkedinPostEdit('${escapeHtml(p.id)}')">Editar</button>
                       <button type="button" class="btn-post-redo" onclick="regenerateLinkedinPost('${escapeHtml(p.id)}')">Refazer</button>`;
                  return `
                    <div class="${cls}" data-post-id="${escapeHtml(p.id)}">
                      <div class="li-post-head">
                        <span class="li-post-type">${escapeHtml(linkedinPostTypeLabel(p.content_type))}</span>
                        ${statusLabel}
                      </div>
                      <h4 class="li-post-title">${escapeHtml(p.title || "")}</h4>
                      ${bodyBlock}
                      ${p.hook ? `<motion class="li-post-meta"><strong>Gancho:</strong> ${escapeHtml(p.hook)}</motion>` : ""}
                      ${p.cta ? `<motion class="li-post-meta"><strong>CTA:</strong> ${escapeHtml(p.cta)}</motion>` : ""}
                      ${p.angle ? `<motion class="li-post-meta"><strong>Ângulo:</strong> ${escapeHtml(p.angle)}</motion>` : ""}
                      <div class="li-post-actions">${actions}</motion>
                    </motion>
                  `;
                }).join("").replace(/<motion/g, "<div").replace(/<\/motion>/g, "</div>");
              }

              function approveLinkedinPost(id) {
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p) return;
                p.status = "approved";
                renderLinkedinPostsContainer();
              }

              function startLinkedinPostEdit(id) {
                linkedinGeneratedPosts.forEach((x) => { if (x.status === "editing") x.status = "draft"; });
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p) return;
                p.bodyEdit = p.body;
                p.status = "editing";
                renderLinkedinPostsContainer();
              }

              function cancelLinkedinPostEdit(id) {
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p) return;
                p.status = p.status === "approved" ? "approved" : "draft";
                delete p.bodyEdit;
                renderLinkedinPostsContainer();
              }

              function saveLinkedinPostEdit(id) {
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p) return;
                const ta = document.getElementById("edit-area-" + id);
                if (ta) p.body = ta.value.trim() || p.body;
                delete p.bodyEdit;
                p.status = "draft";
                renderLinkedinPostsContainer();
              }

              function deleteLinkedinPost(id) {
                if (!confirm("Apagar este post?")) return;
                linkedinGeneratedPosts = linkedinGeneratedPosts.filter((x) => x.id !== id);
                renderLinkedinPostsContainer();
              }

              async function regenerateLinkedinPost(id) {
                const p = linkedinGeneratedPosts.find((x) => x.id === id);
                if (!p || !linkedinAnalysisSnapshot) return;
                const instr = window.prompt("Instruções para refazer (opcional):", "") || "";
                const card = document.querySelector(`[data-post-id="${id}"]`);
                if (card) card.style.opacity = "0.55";
                try {
                  const res = await fetch("/agents/linkedin/regenerate-post", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      analysis: linkedinAnalysisSnapshot,
                      public_profile_data: linkedinAnalysisSnapshot.public_profile_data || {},
                      profile_url: linkedinAnalysisSnapshot.profile_url || "",
                      post: { id: p.id, content_type: p.content_type, title: p.title, body: p.body, hook: p.hook, cta: p.cta, angle: p.angle },
                      edit_instructions: instr || null,
                      language: "pt-PT",
                    }),
                  });
                  const json = await res.json();
                  if (!res.ok) throw new Error(json.detail || JSON.stringify(json));
                  const updated = json.post || {};
                  Object.assign(p, updated, { id: p.id, status: "draft" });
                  delete p.bodyEdit;
                  renderLinkedinPostsContainer();
                } catch (e) {
                  alert("Erro ao refazer: " + (e.message || e));
                } finally {
                  if (card) card.style.opacity = "1";
                }
              }

              async function generateLinkedinPostsFromSnapshot() {
                if (!linkedinAnalysisSnapshot) {
                  alert("Faz primeiro uma análise de perfil.");
                  return;
                }
                const el = document.getElementById("linkedinPostsContainer");
                if (el) el.innerHTML = '<div class="li-posts-loading">A gerar posts com IA…</div>';
                try {
                  const res = await fetch("/agents/linkedin/generate-posts", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      analysis: linkedinAnalysisSnapshot,
                      public_profile_data: linkedinAnalysisSnapshot.public_profile_data || {},
                      profile_url: linkedinAnalysisSnapshot.profile_url || "",
                      count: 3,
                      language: "pt-PT",
                    }),
                  });
                  const json = await res.json();
                  if (!res.ok) throw new Error(json.detail || JSON.stringify(json));
                  linkedinGeneratedPosts = (json.posts || []).map((row) => ({
                    ...row,
                    status: "draft",
                  }));
                  renderLinkedinPostsContainer();
                  const actionsTab = document.querySelector('.tab[data-target="actions"]');
                  if (actionsTab) actionsTab.click();
                } catch (e) {
                  if (el) el.innerHTML = `<div class="err">Erro: ${escapeHtml(e.message || String(e))}</div>`;
                }
              }

"""

POSTS_JS = POSTS_JS.replace("<motion", "<motion").replace("motion>", "motion>")
POSTS_JS = POSTS_JS.replace("<motion", "<motion").replace("</motion>", "</motion>")
# fix motion typos in POSTS_JS
POSTS_JS = POSTS_JS.replace("<motion", "<div").replace("</motion>", "</motion>")
POSTS_JS = POSTS_JS.replace('</motion>', '</motion>').replace('class="li-post-meta"><strong>', 'class="li-post-meta"><strong>')
POSTS_JS = POSTS_JS.replace("</motion>", "</div>").replace('<motion ', "<motion ")

# simpler - fix all motion in POSTS_JS to div
import re
POSTS_JS = POSTS_JS.replace("motion>", "div>")
POSTS_JS = POSTS_JS.replace("<motion", "<div")

if "linkedinAnalysisSnapshot" not in h:
    h = h.replace("              const profileInput = document.getElementById", POSTS_JS + "              const profileInput = document.getElementById")

# After analysis - snapshot + generate posts
ANCHOR = "                  attachTabHandlers();\n                  const resolvedUrl = data.profile_url"
NEW_ANCHOR = """                  attachTabHandlers();
                  setLinkedinAnalysisSnapshot(data);
                  generateLinkedinPostsFromSnapshot();
                  const resolvedUrl = data.profile_url"""

if "setLinkedinAnalysisSnapshot(data)" not in h:
    if ANCHOR in h:
        h = h.replace(ANCHOR, NEW_ANCHOR)
    else:
        h = h.replace("attachTabHandlers();", "attachTabHandlers();\n                  setLinkedinAnalysisSnapshot(data);\n                  generateLinkedinPostsFromSnapshot();", 1)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "linkedinPostsContainer" in h, "generateLinkedinPostsFromSnapshot" in h)
