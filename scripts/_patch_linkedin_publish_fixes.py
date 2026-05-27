"""Corrige publicação no calendário (post errado), imagem por scope e OAuth persistente."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_PATH = ROOT / "agents" / "linkedin_perfil_page.py"


def load_html() -> str:
    """Carrega o HTML embutido a partir do ficheiro (json.dumps)."""
    raw = PAGE_PATH.read_text(encoding="utf-8")
    _prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
    rest = rest.strip()
    if rest.startswith('"'):
        import json
        return json.loads(rest)
    import ast
    return ast.literal_eval(rest)


def save_html(h: str) -> None:
    """Grava o HTML em json.dumps para compatibilidade com outros patches."""
    import json
    header = PAGE_PATH.read_text(encoding="utf-8").split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[0]
    PAGE_PATH.write_text(
        header + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Aplica patches ao HTML embutido do agente LinkedIn (perfil)."""

    h = load_html()

    old_find = """function findLinkedinPostEntry(id) {
                let p = linkedinPostsTabPosts.find((x) => x.id === id);
                if (p) return { post: p, scope: "posts" };
                p = linkedinCalendarPosts.find((x) => x.id === id);
                if (p) return { post: p, scope: "calendar" };
                return { post: null, scope: "posts" };
              }"""

    new_find = """function findLinkedinPostEntry(id, preferredScope) {
                const scopes = preferredScope === "calendar"
                  ? ["calendar", "posts"]
                  : preferredScope === "posts"
                    ? ["posts", "calendar"]
                    : ["calendar", "posts"];
                for (const sc of scopes) {
                  const list = sc === "calendar" ? linkedinCalendarPosts : linkedinPostsTabPosts;
                  const p = list.find((x) => x.id === id);
                  if (p) return { post: p, scope: sc };
                }
                return { post: null, scope: preferredScope || "calendar" };
              }"""

    if old_find not in h:
        raise SystemExit("findLinkedinPostEntry block not found")
    h = h.replace(old_find, new_find, 1)

    replacements = [
        ("findLinkedinPostEntry(id)", "findLinkedinPostEntry(id, scope)"),
        ("findLinkedinPostEntry(p.id)", "findLinkedinPostEntry(p.id, scope)"),
    ]
    for old, new in replacements:
        h = h.replace(old, new)

    # publishLinkedinPost: lookup with scope first
    h = h.replace(
        "async function publishLinkedinPost(id, includeImage, scope) {\n                const entry = findLinkedinPostEntry(id, scope);",
        "async function publishLinkedinPost(id, includeImage, scope) {\n                scope = scope || \"calendar\";\n                const entry = findLinkedinPostEntry(id, scope);",
        1,
    )

    # Persistir estado publicado no calendário
    old_finally = """                } finally {
                  p.publishing_linkedin = false;
                  refreshLinkedinPostScope(scope);
                }
              }

async function regenerateLinkedinPostImage"""

    new_finally = """                } finally {
                  p.publishing_linkedin = false;
                  refreshLinkedinPostScope(scope);
                  if (scope === "calendar" && linkedinCalendarPosts.length) {
                    await saveLinkedinCalendarPostsToDatabase();
                  }
                }
              }

async function regenerateLinkedinPostImage"""

    if old_finally not in h:
        raise SystemExit("publishLinkedinPost finally block not found")
    h = h.replace(old_finally, new_finally, 1)

    # Imagem: incluir id e scheduled_date no pedido
    old_img_body = """                      post: {
                        id: p.id,
                        title: p.title,
                        body: p.body,
                        hook: p.hook,
                        cta: p.cta,
                        content_type: p.content_type,
                      },
                      edit_instructions: editInstructions || null,"""

    new_img_body = """                      post: {
                        id: p.id,
                        title: p.title,
                        body: p.body,
                        hook: p.hook,
                        cta: p.cta,
                        angle: p.angle,
                        content_type: p.content_type,
                        scheduled_date: p.scheduled_date || null,
                      },
                      edit_instructions: editInstructions || null,"""

    if old_img_body not in h:
        raise SystemExit("generate-post-image body not found")
    h = h.replace(old_img_body, new_img_body, 1)

    # OAuth: return path + persistência servidor
    old_connect = """              function connectLinkedinPublish() {
                window.location.href = "/agents/linkedin/connect-publish";
              }"""

    new_connect = """              function buildLinkedinPublishReturnPath() {
                const path = window.location.pathname || "/agentes/linkedin-perfil";
                const params = new URLSearchParams(window.location.search || "");
                params.delete("publish_connected");
                params.delete("publish_error");
                if (linkedinCalendarModalDateKey) {
                  params.set("cal_day", linkedinCalendarModalDateKey);
                  params.set("li_tab", "calendario");
                }
                const qs = params.toString();
                return qs ? path + "?" + qs : path;
              }

              async function connectLinkedinPublish() {
                const ctx = await getLinkedinSupabaseSession();
                if (!ctx || !ctx.session) {
                  alert("Inicia sessão com LinkedIn (Supabase) antes de autorizar publicação.");
                  return;
                }
                if (linkedinPublishAuthorizedServer || (await syncLinkedinPublishAuthFromServer(ctx.session))) {
                  alert("Publicação no LinkedIn já está autorizada para esta conta.");
                  refreshLinkedinPostScope("calendar");
                  refreshLinkedinPostScope("posts");
                  return;
                }
                const returnPath = buildLinkedinPublishReturnPath();
                try {
                  sessionStorage.setItem("linkedin_publish_return_path", returnPath);
                } catch (e) {}
                window.location.href =
                  "/agents/linkedin/connect-publish?return_path=" + encodeURIComponent(returnPath);
              }"""

    if old_connect not in h:
        raise SystemExit("connectLinkedinPublish not found")
    h = h.replace(old_connect, new_connect, 1)

    old_oauth_return = """              (function handlePublishOAuthReturn() {
                try {
                  const q = new URLSearchParams(window.location.search);
                  if (q.get("publish_connected") === "1") {
                    history.replaceState({}, "", window.location.pathname);
                  }
                } catch (e) {}
              })();"""

    new_oauth_return = """              let linkedinPublishAuthorizedServer = false;

              async function syncLinkedinPublishAuthFromServer(session) {
                if (!session || !session.access_token) return false;
                try {
                  const resp = await fetch("/agents/linkedin/publish-auth/status", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ supabase_access_token: session.access_token }),
                  });
                  const data = await resp.json().catch(() => ({}));
                  linkedinPublishAuthorizedServer = !!(data && data.authorized);
                  return linkedinPublishAuthorizedServer;
                } catch (e) {
                  return false;
                }
              }

              async function persistLinkedinPublishAuthToServer(session) {
                if (!session || !session.access_token) return false;
                const publishTok = getPersistedLinkedinPublishToken();
                if (!publishTok) return false;
                let personUrn = "";
                try {
                  personUrn = sessionStorage.getItem(LINKEDIN_PUBLISH_URN_KEY) || "";
                } catch (e) {}
                let expiresIn = 0;
                try {
                  const exp = Number(sessionStorage.getItem(LINKEDIN_PUBLISH_EXPIRES_KEY) || 0);
                  if (exp > Date.now()) expiresIn = Math.max(60, Math.floor((exp - Date.now()) / 1000));
                } catch (e) {}
                try {
                  const resp = await fetch("/agents/linkedin/publish-auth/store", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      supabase_access_token: session.access_token,
                      linkedin_publish_access_token: publishTok,
                      linkedin_person_urn: personUrn || null,
                      expires_in: expiresIn || null,
                    }),
                  });
                  if (!resp.ok) return false;
                  linkedinPublishAuthorizedServer = true;
                  return true;
                } catch (e) {
                  return false;
                }
              }

              function restoreLinkedinPageAfterPublishOAuth() {
                try {
                  const q = new URLSearchParams(window.location.search);
                  const calDay = q.get("cal_day");
                  const liTab = q.get("li_tab");
                  if (liTab === "calendario") {
                    const tabBtn = document.querySelector('.tab[data-target="calendar"]');
                    if (tabBtn && typeof tabBtn.click === "function") tabBtn.click();
                  }
                  if (calDay) openLinkedinCalendarDayModal(calDay);
                  q.delete("publish_connected");
                  q.delete("publish_error");
                  const qs = q.toString();
                  const clean = window.location.pathname + (qs ? "?" + qs : "");
                  history.replaceState({}, "", clean);
                } catch (e) {}
              }

              (async function handlePublishOAuthReturn() {
                try {
                  const q = new URLSearchParams(window.location.search);
                  if (q.get("publish_connected") !== "1" && q.get("publish_error") !== "1") return;
                  const ctx = await getLinkedinSupabaseSession();
                  if (q.get("publish_connected") === "1" && ctx && ctx.session) {
                    await persistLinkedinPublishAuthToServer(ctx.session);
                  }
                  restoreLinkedinPageAfterPublishOAuth();
                  if (typeof refreshLinkedinPostScope === "function") {
                    refreshLinkedinPostScope("calendar");
                    refreshLinkedinPostScope("posts");
                  }
                } catch (e) {}
              })();"""

    if old_oauth_return not in h:
        raise SystemExit("handlePublishOAuthReturn not found")
    h = h.replace(old_oauth_return, new_oauth_return, 1)

    old_has_auth = """              function hasLinkedinPublishAuthorization() {
                return Boolean(getPersistedLinkedinPublishToken());
              }"""

    new_has_auth = """              function hasLinkedinPublishAuthorization() {
                if (linkedinPublishAuthorizedServer) return true;
                return Boolean(getPersistedLinkedinPublishToken());
              }"""

    if old_has_auth not in h:
        raise SystemExit("hasLinkedinPublishAuthorization not found")
    h = h.replace(old_has_auth, new_has_auth, 1)

    # Após login Supabase, sincronizar autorização guardada (definida mais abaixo; hoisted)
    sess_return = """                const { data, error } = await sb.auth.getSession();
                if (error || !data.session) return null;
                return { sb, session: data.session };
              }"""

    sess_return_new = """                const { data, error } = await sb.auth.getSession();
                if (error || !data.session) return null;
                const ctx = { sb, session: data.session };
                void syncLinkedinPublishAuthFromServer(data.session);
                return ctx;
              }"""

    if sess_return not in h:
        raise SystemExit("getLinkedinSupabaseSession return not found")
    h = h.replace(sess_return, sess_return_new, 1)

    # Validar post id no payload de publicação
    old_payload_post = """                  post: {
                    id: p.id,
                    title: p.title,
                    body: p.body,
                    hook: p.hook,
                    cta: p.cta,
                    content_type: p.content_type,
                    generated_image_url: p.generated_image_url || null,
                    status: p.status,
                    image_status: p.image_status || null,
                  },"""

    new_payload_post = """                  post: {
                    id: p.id,
                    title: p.title,
                    body: p.body,
                    hook: p.hook,
                    cta: p.cta,
                    angle: p.angle,
                    content_type: p.content_type,
                    scheduled_date: p.scheduled_date || null,
                    generated_image_url: p.generated_image_url || null,
                    status: p.status,
                    image_status: p.image_status || null,
                  },"""

    if old_payload_post not in h:
        raise SystemExit("publish payload post block not found")
    h = h.replace(old_payload_post, new_payload_post, 1)

    old_pub_tok_check = """                const publishTok = getPersistedLinkedinPublishToken();
                if (!publishTok) {
                  alert("Primeiro clica em «Autorizar publicação no LinkedIn» na secção Publicar.");
                  return;
                }"""

    new_pub_tok_check = """                let publishTok = getPersistedLinkedinPublishToken();
                if (!publishTok && !linkedinPublishAuthorizedServer) {
                  const ctxAuth = await getLinkedinSupabaseSession();
                  if (ctxAuth && ctxAuth.session) {
                    await syncLinkedinPublishAuthFromServer(ctxAuth.session);
                  }
                }
                publishTok = getPersistedLinkedinPublishToken();
                if (!publishTok && !linkedinPublishAuthorizedServer) {
                  alert("Primeiro clica em «Autorizar publicação no LinkedIn» na secção Publicar.");
                  return;
                }"""

    if old_pub_tok_check not in h:
        raise SystemExit("publish token check not found")
    h = h.replace(old_pub_tok_check, new_pub_tok_check, 1)

    save_html(h)
    print("ok", PAGE_PATH)


if __name__ == "__main__":
    main()
