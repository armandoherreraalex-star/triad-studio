"""Gestor de proyectos: creación, ejecución en segundo plano, estado y exportación."""
import json
import os
import shlex
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

from .templates import EXPORTS_DIR, IGNORE_DIRS, PROJECTS_DIR, REGISTRY, PLACEHOLDER


class ProjectManager:
    def __init__(self):
        self._procs: dict = {}

    # ---------- utilidades ----------
    def _dir(self, slug: str) -> Path:
        safe = re_sub_slug(slug)
        target = (PROJECTS_DIR / safe).resolve()
        if not str(target).startswith(str(PROJECTS_DIR.resolve())):
            raise ValueError("Proyecto fuera del área permitida.")
        if not target.is_dir():
            raise FileNotFoundError(f"No existe el proyecto '{safe}'.")
        return target

    def _meta(self, slug: str) -> dict:
        path = self._dir(slug) / "project.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def status(self, slug: str) -> str:
        if slug in self._procs and self._procs[slug].poll() is None:
            return "running"
        pid_file = self._dir(slug) / "project.pid"
        if pid_file.exists():
            try:
                if self._alive(int(pid_file.read_text().strip())):
                    return "running"
            except ValueError:
                pass
        return "stopped"

    # ---------- operaciones ----------
    def list(self) -> list:
        out = []
        if not PROJECTS_DIR.exists():
            return out
        for folder in sorted(PROJECTS_DIR.iterdir()):
            meta_file = folder / "project.json"
            if not meta_file.is_file():
                continue
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            try:
                state = self.status(meta["slug"])
            except Exception:
                state = "desconocido"
            out.append({"slug": meta["slug"], "name": meta.get("name", folder.name),
                        "template": meta.get("template", "?"),
                        "created": meta.get("created", ""),
                        "files": meta.get("files", 0), "status": state})
        return out

    def start(self, slug: str, command: str = "serve") -> dict:
        from .tools import ALLOWED_COMMANDS  # importación perezosa, evita ciclos
        meta = self._meta(slug)
        project_dir = self._dir(slug)
        commands = REGISTRY.get(meta["template"], {}).get("dev_commands", {})
        if command not in commands:
            raise ValueError(f"Comando '{command}' no disponible. Opciones: {', '.join(commands) or '(ninguno)'}")
        if self.status(slug) == "running":
            return {"ok": True, "slug": slug, "note": "ya estaba en ejecución"}

        raw = PLACEHOLDER.sub(lambda m: str(meta.get("vars", {}).get(m.group(1), "")),
                              commands[command])
        parts = shlex.split(raw)
        if not parts:
            raise ValueError("Comando vacío.")
        if parts[0] == "python":
            parts[0] = sys.executable
        base = os.path.basename(parts[0]).lower().replace(".exe", "")
        if base not in ALLOWED_COMMANDS and base not in ("python", "python3"):
            raise PermissionError(f"Comando no autorizado: {parts[0]}")

        log_path = project_dir / "project.log"
        log = open(log_path, "ab")
        proc = subprocess.Popen(
            parts, cwd=str(project_dir), stdout=log, stderr=subprocess.STDOUT,
            start_new_session=(os.name != "nt"))
        (project_dir / "project.pid").write_text(str(proc.pid), encoding="utf-8")
        self._procs[slug] = proc
        return {"ok": True, "slug": slug, "pid": proc.pid, "command": raw, "log": str(log_path)}

    def stop(self, slug: str) -> dict:
        proc = self._procs.pop(slug, None)
        pid_file = self._dir(slug) / "project.pid"
        pid = None
        if proc is not None and proc.poll() is None:
            pid = proc.pid
        elif pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
            except ValueError:
                pid = None
        if pid and self._alive(pid):
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                   capture_output=True, timeout=15)
                else:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
            except Exception:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
        pid_file.unlink(missing_ok=True)
        return {"ok": True, "slug": slug, "estado": "detenido"}

    def install(self, slug: str) -> str:
        from .tools import ALLOWED_COMMANDS
        meta = self._meta(slug)
        project_dir = self._dir(slug)
        commands = REGISTRY.get(meta["template"], {}).get("install", [])
        if not commands:
            return "Este proyecto no requiere instalación de dependencias."
        outputs = []
        for cmd in commands:
            parts = shlex.split(cmd)
            if parts and parts[0] == "python":
                parts[0] = sys.executable
            base = os.path.basename(parts[0]).lower().replace(".exe", "")
            if base not in ALLOWED_COMMANDS and base not in ("python", "python3"):
                outputs.append(f"omitido (no autorizado): {cmd}")
                continue
            proc = subprocess.run(parts, cwd=str(project_dir), capture_output=True,
                                  text=True, timeout=300)
            outputs.append(f"$ {cmd}\n{(proc.stdout or '')[-2500:]}{(proc.stderr or '')[-1500:]}")
        return "\n".join(outputs)[:9000]

    def export(self, slug: str) -> str:
        project_dir = self._dir(slug)
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = EXPORTS_DIR / f"{slug}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in project_dir.rglob("*"):
                rel = item.relative_to(project_dir)
                if any(part in IGNORE_DIRS for part in rel.parts):
                    continue
                if item.name in ("project.log", "project.pid"):
                    continue
                if item.is_file():
                    zf.write(item, rel)
        return str(zip_path)

    def log_tail(self, slug: str, lines: int = 40) -> str:
        log_path = self._dir(slug) / "project.log"
        if not log_path.exists():
            return "Sin registro todavía."
        content = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(content[-lines:]) or "Registro vacío."


def re_sub_slug(slug: str) -> str:
    import re
    return re.sub(r"[^a-z0-9\-]", "", (slug or "").lower())[:64]


project_manager = ProjectManager()