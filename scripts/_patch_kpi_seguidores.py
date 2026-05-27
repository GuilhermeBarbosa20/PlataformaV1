# -*- coding: utf-8 -*-
"""KPI topo: perfil pessoal mostra Seguidores (harvest followerCount), não Ligações."""
import json
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())

OLD = """              function formatLinkedinAudienceCount(count) {
                if (count === null || count === undefined || count === "") {
                  return "Dado não público no LinkedIn";
                }
                const n = Number(count);
                if (Number.isNaN(n)) return String(count);
                return formatNumber(n);
              }"""

NEW = """              function parseLinkedinMetricNumber(value) {
                if (value === null || value === undefined || value === "") return null;
                if (typeof value === "number" && !Number.isNaN(value)) return value;
                const text = String(value).trim().replace(/\\s/g, "");
                if (!text || /dado\\s+n[aã]o\\s+p[uú]blico/i.test(text)) return null;
                const normalized = text.replace(/\\.(?=\\d{3})/g, "").replace(",", ".");
                const n = Number(normalized);
                return Number.isNaN(n) ? null : n;
              }

              function linkedinProfileIsOrganization(data, profile) {
                const url = String(data.profile_url || profile.profile_url || data.linkedin_profile_url || "").toLowerCase();
                if (url.includes("/company/") || url.includes("/school/")) return true;
                const metrics = data.metricas_linkedin || data.metricas_instagram || {};
                if (metrics.universalName || metrics.tagline || metrics.name) {
                  if (!url.includes("/in/")) return true;
                }
                return false;
              }

              function linkedinKpiAudienceCount(data, profile) {
                const metrics = data.metricas_linkedin || data.metricas_instagram || {};
                const harvest = (profile && profile.harvest_profile) || {};
                const candidates = [
                  harvest.followerCount,
                  harvest.followers_count,
                  profile.followers_count,
                  profile.connections_count,
                  metrics.followerCount,
                  metrics.seguidores,
                  metrics.connectionsCount,
                  metrics.ligacoes,
                ];
                for (const c of candidates) {
                  const n = parseLinkedinMetricNumber(c);
                  if (n !== null) return n;
                }
                return null;
              }

              function formatLinkedinAudienceCount(count) {
                const n = parseLinkedinMetricNumber(count);
                if (n === null) return "Dado não público no LinkedIn";
                return formatNumber(n);
              }"""

if OLD not in h:
    raise SystemExit("formatLinkedinAudienceCount block not found")
h = h.replace(OLD, NEW, 1)

OLD_KPI = """                const kpis = [
                  { label: (String(data.profile_url || profile.profile_url || "").toLowerCase().includes("/company/") || String(data.profile_url || profile.profile_url || "").toLowerCase().includes("/school/")) ? "Seguidores" : "Ligações", value: formatLinkedinAudienceCount(profile.followers_count), sub: profile.employer ? String(profile.employer).slice(0, 40) : "", accent: true },"""

NEW_KPI = """                const isOrg = linkedinProfileIsOrganization(data, profile);
                const audienceCount = linkedinKpiAudienceCount(data, profile);
                const audienceLabel = isOrg ? "Seguidores" : "Seguidores";
                const audienceSub = isOrg
                  ? (profile.employer || profile.tagline ? String(profile.employer || profile.tagline).slice(0, 40) : "")
                  : (profile.headline ? String(profile.headline).slice(0, 50) : (profile.employer ? String(profile.employer).slice(0, 40) : ""));
                const kpis = [
                  { label: audienceLabel, value: formatLinkedinAudienceCount(audienceCount), sub: audienceSub, accent: true },"""

if OLD_KPI not in h:
    raise SystemExit("kpis array line not found")
h = h.replace(OLD_KPI, NEW_KPI, 1)

PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", "linkedinKpiAudienceCount" in h)
