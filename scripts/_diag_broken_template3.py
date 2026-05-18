# -*- coding: utf-8 -*-
import json
from pathlib import Path
h = json.loads((Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8").split("=",1)[1].strip())

print("Around script end (82800-84000):")
print(h[82800:84050])

print("\n--- find </script> ---")
i = h.rfind("</script>")
print(f"</script> at {i}")
print(repr(h[i-200:i+100]))
