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