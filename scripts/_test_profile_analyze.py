import json
import sys
import urllib.request

sys.path.insert(0, ".")
from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML

if "sourabh" in LINKEDIN_PERFIL_PAGE_HTML:
    print("HTML contains sourabh!")
else:
    print("HTML ok, no sourabh")

body = json.dumps(
    {
        "platform": "linkedin",
        "profile_input": "https://www.linkedin.com/in/williamhgates/",
        "language": "pt",
    }
).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/agents/social-media/profile-analyze",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=300) as resp:
        print("status", resp.status)
        print(resp.read()[:200])
except urllib.error.HTTPError as e:
    err = e.read().decode()
    print("HTTP", e.code)
    print(err[:800])
    if "sourabh" in err:
        print(">>> STILL SOURABH IN RESPONSE")
