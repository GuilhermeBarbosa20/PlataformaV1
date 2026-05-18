import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=", 1)[1].strip())
checks = [
    "getStoredLinkedinProfileUrl",
    "captureLinkedinOAuthTokens",
    "appendLinkedinSessionFields",
    "stored_linkedin_profile_url",
    "linkedin_id_token",
    "onAuthStateChange",
    'profile_input: profileValue',
    "await tryResolveLinkedinProfileUrl(ctx.sb)",
]
for c in checks:
    print(c, c in h)
i = h.find("if (autoAuthenticated)")
print("\n", h[i:i+1200])
