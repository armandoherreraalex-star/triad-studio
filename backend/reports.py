"""Generación de informes HTML con estilo profesional (abrible en cualquier navegador)."""
import re
from datetime import datetime

from .config import REPORTS_DIR

_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<style>
  :root {{ --ink:#121826; --paper:#f7f5f0; --accent:#1f4b99; --rule:#d9d2c3; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--paper); color:var(--ink);
         font-family:'Source Serif 4',Georgia,serif; line-height:1.72; }}
  .sheet {{ max-width:820px; margin:0 auto; padding:72px 64px 96px; }}
  header {{ border-bottom:3px solid var(--accent); padding-bottom:22px; margin-bottom:38px; }}
  .kicker {{ font-family:'Chakra Petch',sans-serif; letter-spacing:.32em;
             text-transform:uppercase; font-size:11px; color:var(--accent); }}
  h1 {{ font-family:'Chakra Petch',sans-serif; font-size:38px; margin:10px 0 6px; line-height:1.12; }}
  .meta {{ font-family:'Chakra Petch',sans-serif; font-size:12.5px; color:#5a6272; letter-spacing:.05em; }}
  h2 {{ font-family:'Chakra Petch',sans-serif; font-size:21px; margin:44px 0 12px;
        padding-left:14px; border-left:4px solid var(--accent); }}
  p {{ margin:0 0 15px; text-align:justify; }}
  table {{ width:100%; border-collapse:collapse; margin:22px 0; font-size:14.5px; }}
  th {{ background:var(--accent); color:#fff; font-family:'Chakra Petch',sans-serif;
        text-align:left; padding:10px 14px; letter-spacing:.04em; }}
  td {{ border-bottom:1px solid var(--rule); padding:11px 14px; }}
  ul {{ margin:0 0 18px; padding-left:22px; }}
  footer {{ margin-top:64px; border-top:1px solid var(--rule); padding-top:18px;
            font-family:'Chakra Petch',sans-serif; font-size:11px; letter-spacing:.18em;
            text-transform:uppercase; color:#7a8291; }}
  @media print {{ body {{ background:#fff; }} .sheet {{ padding:0; }} }}
</style>
</head>
<body>
<div class="sheet">
  <header>
    <div class="kicker">{kicker}</div>
    <h1>{title}</h1>
    <div class="meta">{meta}</div>
  </header>
  {body}
  <footer>Generado por TRIAD STUDIO · Sylphiette · Roxy Migurdia · Eris Boreas Greyrat</footer>
</div>
</body>
</html>"""


def _render_body(content: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", content) if b.strip()]
    html = []
    for block in blocks:
        if block.startswith("#"):
            text = block.lstrip("# ").strip()
            html.append(f"<h2>{text}</h2>")
        elif block.startswith(("-", "*")):
            items = [f"<li>{line.lstrip('-* ').strip()}</li>"
                     for line in block.splitlines() if line.strip()]
            html.append("<ul>" + "".join(items) + "</ul>")
        elif "|" in block and block.count("|") >= 2:
            rows = [r for r in block.splitlines() if "|" in r]
            parsed = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            parsed = [r for r in parsed if not all(set(c) <= {"-", " "} for c in r)]
            if parsed:
                head = parsed[0]
                html.append("<table><thead><tr>" +
                            "".join(f"<th>{c}</th>" for c in head) +
                            "</tr></thead><tbody>" +
                            "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
                                    for row in parsed[1:]) + "</tbody></table>")
        else:
            html.append(f"<p>{block}</p>")
    return "\n".join(html)


def build_report(title: str, content: str, style: str = "universitario") -> str:
    style = (style or "universitario").lower()
    kicker = ("Informe Académico" if "univ" in style or "acad" in style
              else "Informe Corporativo" if "empr" in style or "corp" in style
              else "Informe Técnico")
    stamp = datetime.now().strftime("%d de %B de %Y · %H:%M")
    html = _TEMPLATE.format(title=title, kicker=kicker, meta=stamp,
                            body=_render_body(content or "Sin contenido."))
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "informe"
    path = REPORTS_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)