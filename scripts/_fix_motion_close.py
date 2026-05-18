import json
from pathlib import Path
PAGE = Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py"
raw = PAGE.read_text(encoding="utf-8")
prefix, rest = raw.split("LINKEDIN_PERFIL_PAGE_HTML: str = ", 1)
h = json.loads(rest.strip())
h = h.replace(
    "metricas_instagram)}\n                      </motion>\n                    </motion>",
    "metricas_instagram)}\n                      </div>\n                    </div>",
)
h = h.replace(
    "metricas_instagram)}\n                      </div>\n                    </motion>",
    "metricas_instagram)}\n                      </div>\n                    </div>",
)
PAGE.write_text(prefix + "LINKEDIN_PERFIL_PAGE_HTML: str = " + json.dumps(h, ensure_ascii=False) + "\n", encoding="utf-8")
print("motion close left:", h.count("</motion>"))
