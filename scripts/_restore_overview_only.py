# -*- coding: utf-8 -*-
"""Restaura Visão Geral (harvest + métricas) sem alterar resto; grava em json.dumps."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "agents" / "linkedin_perfil_page.py"


def load_html() -> str:
    raw = PAGE.read_text(encoding="utf-8")
    _prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
    rest = rest.strip()
    if rest.startswith('"') or rest.startswith("'"):
        return ast.literal_eval(rest)
    return json.loads(rest)


def save_html(h: str) -> None:
    header = '''"""Página HTML do agente LinkedIn (perfil), embutida no backend Python.

O conteúdo é servido por ``app.py`` via ``LINKEDIN_PERFIL_PAGE_HTML``.
"""

from __future__ import annotations

LINKEDIN_PERFIL_PAGE_HTML: str = '''
    PAGE.write_text(
        header + json.dumps(h, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_patch_script(name: str) -> bool:
    path = ROOT / "scripts" / name
    if not path.exists():
        return False
    r = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"SKIP {name}: {r.stderr or r.stdout}")
        return False
    print(f"OK {name}: {(r.stdout or '').strip()}")
    return True


def main() -> None:
    h = load_html()

    # Garantir formato json para patches existentes
    save_html(h)

    overview_patches = [
        "_patch_overview_metrics_only.py",
        "_patch_linkedin_metrics_ui.py",
        "_patch_harvest_overview_ui.py",
        "_patch_harvest_all_fields_ui.py",
        "_patch_metrics_readable_images.py",
        "_patch_profile_overview_pretty.py",
        "_patch_company_certs_overview.py",
        "_patch_personal_certs_list.py",
        "_patch_kpi_seguidores.py",
    ]

    for name in overview_patches:
        run_patch_script(name)

    # Re-aplicar fixes de publicação (lê do ficheiro, não import)
    run_patch_script("_patch_linkedin_publish_fixes.py")

    h2 = load_html()
    ov = h2.split('id="panel-overview"', 1)[1].split('id="panel-posts"', 1)[0]
    checks = {
        "harvest_fn": "renderLinkedinHarvestProfileOverview" in h2,
        "hero_css": "li-profile-hero" in h2,
        "no_insights_in_ov": "Principais Insights" not in ov,
        "indicadores": "Indicadores de desempenho" in ov,
        "harvest_in_ov": "renderLinkedinHarvestProfileOverview" in ov,
        "publish_scope": "findLinkedinPostEntry(id, preferredScope)" in h2,
        "json_format": PAGE.read_text(encoding="utf-8").split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)[1].strip().startswith('"'),
    }
    print("checks:", checks)
    if not all(checks.values()):
        raise SystemExit("Restore incomplete")


if __name__ == "__main__":
    main()
