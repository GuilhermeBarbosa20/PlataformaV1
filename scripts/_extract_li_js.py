import re
from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML

h = LINKEDIN_PERFIL_PAGE_HTML
for pat in [
    r"profile-analyze.{0,800}",
    r"provider_token.{0,400}",
    r"profile_input.{0,400}",
    r"runAnalyze.{0,1200}",
    r"getSession.{0,600}",
]:
    m = re.search(pat, h, re.DOTALL)
    if m:
        print("===", pat[:30])
        print(m.group(0)[:900])
        print()
