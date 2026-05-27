import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: F401
from agents.linkedin_perfil_page import LINKEDIN_PERFIL_PAGE_HTML as h

checks = [
    "findLinkedinPostEntry(id, preferredScope)",
    "buildLinkedinPublishReturnPath",
    "syncLinkedinPublishAuthFromServer",
    'scope = scope || "calendar"',
    "persistLinkedinPublishAuthToServer",
    "restoreLinkedinPageAfterPublishOAuth",
    "saveLinkedinCalendarPostsToDatabase",
]
for c in checks:
    print(c, "OK" if c in h else "MISSING")
