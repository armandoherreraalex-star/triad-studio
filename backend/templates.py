"""Motor de plantillas: convierte una plantilla en un proyecto completo y funcional."""
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import WORKSPACE_DIR

TEMPLATES_DIR = WORKSPACE_DIR / "templates"
PROJECTS_DIR = WORKSPACE_DIR / "projects"
EXPORTS_DIR = WORKSPACE_DIR / "exports"

for _d in (TEMPLATES_DIR, PROJECTS_DIR, EXPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
              ".ttf", ".otf", ".pdf", ".zip", ".db", ".mp3", ".mp4"}
IGNORE_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv", "dist", "build", ".exec"}

REGISTRY = {
    "fastapi-saas": {
        "title": "API SaaS con FastAPI",
        "description": "Backend profesional con autenticación, CRUD, SQLite y documentación /docs.",
        "vars": {"port": "8001", "author": "TRIAD STUDIO", "description": "Plataforma SaaS generada con FastAPI."},
        "install": ["python -m pip install -r requirements.txt"],
        "dev_commands": {
            "serve": "python -m uvicorn main:app --reload --port {{port}}",
            "test": "python -m pytest -q",
        },
    },
    "react-dashboard": {
        "title": "Panel de control React",
        "description": "Aplicación web con Vite + React: métricas, tablas y navegación profesional.",
        "vars": {"port": "5173", "author": "TRIAD STUDIO", "description": "Panel de control y gestión."},
        "install": ["npm install"],
        "dev_commands": {"serve": "npm run dev", "build": "npm run build"},
    },
    "static-landing": {
        "title": "Landing page profesional",
        "description": "Sitio corporativo con hero, métricas, precios y animaciones de entrada.",
        "vars": {"port": "8080", "author": "TRIAD STUDIO", "description": "Infraestructura digital para equipos que exigen resultados."},
        "install": [],
        "dev_commands": {"serve": "python -m http.server {{port}}"},
    },
    "python-bot": {
        "title": "Bot de automatización",
        "description": "Bot que organiza archivos por tipo y genera informes automáticos periódicos.",
        "vars": {"port": "0", "author": "TRIAD STUDIO", "description": "Organiza archivos y genera informes sin intervención."},
        "install": [],
        "dev_commands": {"serve": "python bot.py", "single": "python bot.py --una-vez"},
    },
    "game-2d": {
        "title": "Juego 2D en navegador",
        "description": "Prototipo jugable con movimiento, combate, inventario, oro, niveles y misiones.",
        "vars": {"port": "8081", "author": "TRIAD STUDIO", "description": "Juego de acción 2D con misiones e inventario."},
        "install": [],
        "dev_commands": {"serve": "python -m http.server {{port}}"},
    },
}


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:48]


def list_templates() -> list:
    out = []
    for key, entry in REGISTRY.items():
        out.append({
            "id": key,
            "title": entry["title"],
            "description": entry["description"],
            "installed": (TEMPLATES_DIR / key).is_dir(),
            "commands": list(entry.get("dev_commands", {}).keys()),
            "vars": entry.get("vars", {}),
        })
    return out


def template_info(template: str) -> dict:
    if template not in REGISTRY:
        raise ValueError(f"Plantilla desconocida: {template}. Disponibles: {', '.join(REGISTRY)}")
    source = TEMPLATES_DIR / template
    files = []
    if source.is_dir():
        files = sorted(str(p.relative_to(source)) for p in source.rglob("*") if p.is_file())
    entry = dict(REGISTRY[template])
    entry["id"] = template
    entry["files"] = files
    entry["installed"] = source.is_dir()
    return entry


def read_template_file(template: str, path: str) -> str:
    source = (TEMPLATES_DIR / template / path).resolve()
    if not str(source).startswith(str(TEMPLATES_DIR.resolve())):
        raise ValueError("Ruta fuera de las plantillas.")
    return source.read_text(encoding="utf-8")[:12000]


def create_project(template: str, name: str, variables: dict | None = None) -> dict:
    if template not in REGISTRY:
        raise ValueError(f"Plantilla desconocida: {template}. Disponibles: {', '.join(REGISTRY)}")
    source = TEMPLATES_DIR / template
    if not source.is_dir():
        raise FileNotFoundError(
            f"La plantilla '{template}' no está instalada. Crea sus archivos en {source}.")

    slug = _slugify(name) or template
    target = PROJECTS_DIR / slug
    if target.exists():
        raise FileExistsError(f"Ya existe un proyecto llamado '{slug}'. Elige otro nombre.")

    values = {
        "project_name": name or template,
        "project_slug": slug,
        "created": datetime.now().strftime("%d/%m/%Y"),
        "version": "1.0.0",
        "author": "TRIAD STUDIO",
    }
    values.update(REGISTRY[template].get("vars", {}))
    values.update({k: str(v) for k, v in (variables or {}).items()})

    files = 0
    for item in sorted(source.rglob("*")):
        rel = item.relative_to(source)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        dest = target / rel
        if item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if item.suffix.lower() in BINARY_EXT:
            shutil.copy2(item, dest)
        else:
            text = item.read_text(encoding="utf-8")
            rendered = PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), "")), text)
            dest.write_text(rendered, encoding="utf-8")
        files += 1

    meta = {
        "name": values["project_name"],
        "slug": slug,
        "template": template,
        "vars": values,
        "files": files,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dev_commands": REGISTRY[template].get("dev_commands", {}),
        "install": REGISTRY[template].get("install", []),
        "path": str(target),
    }
    (target / "project.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta