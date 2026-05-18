from pathlib import Path

raw = (Path(__file__).resolve().parents[1] / "agents" / "linkedin_perfil_page.py").read_text(encoding="utf-8")
html = raw.split('LINKEDIN_PERFIL_PAGE_HTML: str = ', 1)[1]
# decode escapes for readability
import codecs

decoded = codecs.decode(html, "unicode_escape")
out = Path(__file__).parent / "_linkedin_page_decoded_snippet.txt"
# extract renderKpis through next function
start = decoded.find("function renderKpis")
end = decoded.find("function ", start + 20)
chunk = decoded[start : end + 2000]
out.write_text(chunk[:8000], encoding="utf-8")
print("wrote", out, "len", len(chunk))
