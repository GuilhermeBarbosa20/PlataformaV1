# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

print("=== BEFORE first </script> (82500-83060) ===")
print(h[82500:83060])
print("\n=== AFTER first </script> (83051-83800) ===")
print(h[83051:83800])
