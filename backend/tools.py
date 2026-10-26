"""Registro de herramientas ejecutables. Todo opera dentro de workspace/."""
import ast
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict

import httpx

from .config import CUSTOM_TOOLS_DIR, WORKSPACE_DIR, settings
from .memory import memory

ALLOWED_COMMANDS = {"python", "python3", "py", "pip", "pip3", "node", "npm", "npx",
                    "git", "ls", "dir", "echo", "mkdir", "dotnet", "go", "cargo", "ffmpeg"}


def safe_path(path: str) -> Path:
    """Convierte una ruta relativa en ruta segura dentro del workspace."""
    target = (WORKSPACE_DIR / path).resolve()
    if not str(target).startswith(str(WORKSPACE_DIR.resolve())):
        raise ValueError("Ruta fuera del workspace permitido.")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, dict] = {}

    def register(self, name: str, description: str, parameters: dict,
                 handler: Callable[[dict], str]) -> None:
        self._tools[name] = {"name": name, "description": description,
                             "parameters": parameters, "handler": handler}

    def list(self) -> list:
        return [{k: v for k, v in t.items() if k != "handler"} for t in self._tools.values()]

    def execute(self, name: str, args: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Herramienta desconocida: {name}"}, ensure_ascii=False)
        try:
            result = tool["handler"](args or {})
            return str(result)[:12000]
        except Exception as exc:
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)


registry = ToolRegistry()


# ---------------- herramientas base ----------------
def _list_files(args):
    path = safe_path(args.get("path", "."))
    if path.is_file():
        return str(path.relative_to(WORKSPACE_DIR))
    lines = []
    for item in sorted(path.rglob("*")):
        if any(part.startswith(".") for part in item.parts):
            continue
        rel = item.relative_to(WORKSPACE_DIR)
        if item.is_dir():
            lines.append(f"[DIR]  {rel}")
        else:
            lines.append(f"[FILE] {rel}  ({item.stat().st_size} bytes)")
    return "\n".join(lines[:400]) or "El workspace está vacío."


def _read_file(args):
    target = safe_path(args["path"])
    return target.read_text(encoding="utf-8")[:12000]


def _write_file(args):
    target = safe_path(args["path"])
    content = args.get("content", "")
    target.write_text(content, encoding="utf-8")
    return f"Archivo guardado: {target.relative_to(WORKSPACE_DIR)} ({len(content)} caracteres, UTF-8)"


def _create_folder(args):
    target = safe_path(args["path"])
    target.mkdir(parents=True, exist_ok=True)
    return f"Carpeta creada: {target.relative_to(WORKSPACE_DIR)}"


def _search_text(args):
    query = args["query"].lower()
    root = safe_path(args.get("path", "."))
    hits = []
    for item in root.rglob("*"):
        if not item.is_file() or item.suffix.lower() in {".png", ".jpg", ".pdf", ".zip", ".db"}:
            continue
        try:
            for num, line in enumerate(item.read_text(encoding="utf-8").splitlines(), 1):
                if query in line.lower():
                    hits.append(f"{item.relative_to(WORKSPACE_DIR)}:{num}: {line.strip()[:160]}")
        except (UnicodeDecodeError, OSError):
            continue
        if len(hits) >= 120:
            break
    return "\n".join(hits) or f"Sin coincidencias para '{args['query']}'."


def _check_syntax(args):
    code = args.get("code")
    if code is None:
        code = safe_path(args["path"]).read_text(encoding="utf-8")
    try:
        ast.parse(code)
        return "Sintaxis correcta."
    except SyntaxError as exc:
        return f"Error de sintaxis línea {exc.lineno}: {exc.msg}"


def _run_python(args):
    code = args.get("code")
    if code is None:
        code = safe_path(args["path"]).read_text(encoding="utf-8")
    script = WORKSPACE_DIR / ".exec" / "snippet.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(code, encoding="utf-8")
    try:
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                              timeout=settings.command_timeout, cwd=str(WORKSPACE_DIR))
        out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        return out.strip()[:11000] or f"Proceso terminado con código {proc.returncode}."
    except subprocess.TimeoutExpired:
        return f"Tiempo agotado ({settings.command_timeout}s)."


def _run_command(args):
    parts = shlex.split(args["command"])
    if not parts or parts[0].lower() not in ALLOWED_COMMANDS:
        return json.dumps({"error": f"Comando no autorizado: {parts[0] if parts else ''}"})
    proc = subprocess.run(parts, capture_output=True, text=True,
                          timeout=settings.command_timeout, cwd=str(WORKSPACE_DIR))
    return ((proc.stdout or "") + (proc.stderr or "")).strip()[:11000]


def _remember(args):
    mid = memory.store(args["content"], kind=args.get("kind", "general"),
                       tags=args.get("tags", ""), importance=float(args.get("importance", 0.5)))
    return f"Guardado en memoria permanente (id {mid})."


def _recall(args):
    results = memory.search(args["query"], limit=6)
    return json.dumps(results, ensure_ascii=False, indent=2)


def _web_fetch(args):
    r = httpx.get(args["url"], timeout=20, follow_redirects=True)
    text = re.sub(r"<[^>]+>", " ", r.text)
    return re.sub(r"\s+", " ", text)[:8000]


def _build_report(args):
    from .reports import build_report
    path = build_report(args["title"], args.get("content", ""), args.get("style", "universitario"))
    return f"Informe generado: {path}"


registry.register("list_files", "Lista archivos y carpetas del workspace.",
                  {"path": "string opcional"}, _list_files)
registry.register("read_file", "Lee un archivo de texto UTF-8.", {"path": "string"}, _read_file)
registry.register("write_file", "Crea o sobrescribe un archivo UTF-8.",
                  {"path": "string", "content": "string"}, _write_file)
registry.register("create_folder", "Crea una carpeta.", {"path": "string"}, _create_folder)
registry.register("search_text", "Busca texto en todos los archivos del proyecto.",
                  {"query": "string", "path": "string opcional"}, _search_text)
registry.register("check_python_syntax", "Valida sintaxis Python con ast.",
                  {"path": "string", "code": "string opcional"}, _check_syntax)
registry.register("run_python", "Ejecuta código Python aislado con tiempo límite.",
                  {"code": "string", "path": "string opcional"}, _run_python)
registry.register("run_command", "Ejecuta un comando de la lista autorizada.",
                  {"command": "string"}, _run_command)
registry.register("remember", "Guarda información en memoria permanente.",
                  {"content": "string", "kind": "string", "importance": "float"}, _remember)
registry.register("recall", "Busca en la memoria permanente.", {"query": "string"}, _recall)
registry.register("web_fetch", "Descarga una página web pública.", {"url": "string"}, _web_fetch)
registry.register("build_report", "Genera un informe PDF/HTML profesional.",
                  {"title": "string", "content": "string", "style": "string"}, _build_report)


def load_custom_tools() -> int:
    """Importa herramientas creadas por el propio agente en custom_tools/."""
    import importlib.util
    loaded = 0
    for file in sorted(CUSTOM_TOOLS_DIR.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"custom_{file.stem}", file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        meta = getattr(module, "TOOL", None)
        if not meta or "run" not in meta:
            continue
        registry.register(meta["name"], meta.get("description", ""),
                          meta.get("parameters", {}), meta["run"])
        loaded += 1
    return loaded
    
# ================= FASE 2 · FÁBRICA DE APLICACIONES =================

def _scaffold(args):
    from .templates import create_project

    meta = create_project(
        args["template"],
        args.get("name") or args["template"],
        args.get("vars") or {}
    )
    return json.dumps(meta, ensure_ascii=False, indent=2)


def _list_templates(args):
    from .templates import list_templates

    return json.dumps(list_templates(), ensure_ascii=False, indent=2)


def _read_template(args):
    from .templates import read_template_file, template_info

    if args.get("path"):
        return read_template_file(args["template"], args["path"])

    return json.dumps(
        template_info(args["template"]),
        ensure_ascii=False,
        indent=2
    )


def _list_projects(args):
    from .projects import project_manager

    return json.dumps(
        project_manager.list(),
        ensure_ascii=False,
        indent=2
    )


def _run_dev_server(args):
    from .projects import project_manager

    result = project_manager.start(
        args["project"],
        args.get("command", "serve")
    )
    return json.dumps(result, ensure_ascii=False)


def _stop_dev_server(args):
    from .projects import project_manager

    return json.dumps(
        project_manager.stop(args["project"]),
        ensure_ascii=False
    )


def _install_dependencies(args):
    from .projects import project_manager

    return project_manager.install(args["project"])


def _export_project(args):
    from .projects import project_manager

    path = project_manager.export(args["project"])
    return f"Proyecto exportado en: {path}"


def _project_log(args):
    from .projects import project_manager

    return project_manager.log_tail(
        args["project"],
        int(args.get("lines", 40))
    )


def _system_doctor(args):
    import platform
    from .llm import get_engine
    from .templates import list_templates

    lines = [
        f"Python {platform.python_version()} · {platform.system()}"
    ]

    try:
        engine = get_engine()
        connected = engine.__class__.__name__ == "LLMClient"
        lines.append(
            f"Motor de IA: {'conectado' if connected else 'modo offline'}"
        )
    except Exception as exc:
        lines.append(f"Motor de IA: ERROR ({exc})")

    try:
        templates = list_templates()

        for template in templates:
            status = (
                "instalada"
                if template.get("installed", False)
                else "FALTA (crea sus archivos)"
            )
            lines.append(
                f"Plantilla {template.get('id', 'desconocida')}: {status}"
            )
    except Exception as exc:
        lines.append(f"Plantillas: ERROR ({exc})")

    try:
        stats = memory.stats()
        lines.append(
            f"Memoria: {stats['memories']} memorias · "
            f"{stats['tools']} herramientas · "
            f"{stats['learnings']} reglas aprendidas"
        )
    except Exception as exc:
        lines.append(f"Memoria: ERROR ({exc})")

    try:
        probe = WORKSPACE_DIR / ".doctor.txt"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        lines.append("Workspace: escribible")
    except Exception as exc:
        lines.append(f"Workspace: ERROR ({exc})")

    return "\n".join(lines)


# ================= REGISTRO DE HERRAMIENTAS · FASE 2 =================

registry.register(
    "scaffold_project",
    "Crea un proyecto completo desde una plantilla.",
    {
        "template": "string",
        "name": "string",
        "vars": "objeto opcional"
    },
    _scaffold
)

registry.register(
    "list_templates",
    "Lista las plantillas disponibles y su estado.",
    {},
    _list_templates
)

registry.register(
    "read_template",
    "Muestra los archivos o el contenido de una plantilla.",
    {
        "template": "string",
        "path": "string opcional"
    },
    _read_template
)

registry.register(
    "list_projects",
    "Lista los proyectos creados y su estado.",
    {},
    _list_projects
)

registry.register(
    "run_dev_server",
    "Ejecuta un proyecto en segundo plano.",
    {
        "project": "string",
        "command": "string opcional"
    },
    _run_dev_server
)

registry.register(
    "stop_dev_server",
    "Detiene un proyecto en ejecución.",
    {"project": "string"},
    _stop_dev_server
)

registry.register(
    "install_dependencies",
    "Instala las dependencias de un proyecto.",
    {"project": "string"},
    _install_dependencies
)

registry.register(
    "export_project",
    "Exporta un proyecto como archivo ZIP.",
    {"project": "string"},
    _export_project
)

registry.register(
    "project_log",
    "Muestra las últimas líneas del registro de un proyecto.",
    {
        "project": "string",
        "lines": "int opcional"
    },
    _project_log
)

registry.register(
    "system_doctor",
    "Diagnostica el estado del sistema.",
    {},
    _system_doctor
)
