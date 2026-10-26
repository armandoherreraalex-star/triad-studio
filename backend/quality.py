"""Evaluación de calidad: comprobaciones reales sobre los proyectos generados."""
import ast
import json
import subprocess
import sys

from .memory import memory
from .templates import PROJECTS_DIR
from .tools import registry


def run_project_tests(slug: str) -> dict:
    project = (PROJECTS_DIR / slug).resolve()
    if not str(project).startswith(str(PROJECTS_DIR.resolve())) or not project.is_dir():
        return {"error": f"Proyecto no encontrado: {slug}"}

    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})

    add("estructura: project.json", (project / "project.json").is_file())
    add("documentación: README", bool(list(project.glob("README*"))))

    py_files = [f for f in project.rglob("*.py")
                if not any(p in ("node_modules", ".venv", "__pycache__") for p in f.parts)]
    syntax_errors = []
    for f in py_files:
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except Exception as exc:
            syntax_errors.append(f"{f.name}: {exc}")
    add(f"sintaxis Python ({len(py_files)} archivos)", not syntax_errors,
        "; ".join(syntax_errors[:3]))

    html_files = [f for f in project.rglob("*.html") if "node_modules" not in f.parts]
    html_ok = all("</html>" in f.read_text(encoding="utf-8", errors="ignore").lower()
                  for f in html_files) if html_files else True
    add(f"estructura HTML ({len(html_files)} archivos)", html_ok)

    if py_files:
        proc = subprocess.run([sys.executable, "-m", "compileall", "-q", str(project)],
                              capture_output=True, text=True, timeout=120)
        add("compilación Python", proc.returncode == 0,
            (proc.stderr or proc.stdout or "")[:300])

    meta_file = project / "project.json"
    if meta_file.is_file():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            test_cmd = (meta.get("dev_commands") or {}).get("test")
            if test_cmd:
                parts = test_cmd.split()
                if parts[0] == "python":
                    parts[0] = sys.executable
                proc = subprocess.run(parts, cwd=str(project), capture_output=True,
                                      text=True, timeout=180)
                add("batería de pruebas del proyecto", proc.returncode == 0,
                    (proc.stdout or proc.stderr or "")[:300])
        except Exception as exc:
            add("metadatos del proyecto", False, exc)

    passed = sum(1 for c in checks if c["ok"])
    score = round(passed / max(len(checks), 1), 3)
    feedback = ("Proyecto sólido." if score >= 0.8 else
                "Revisar los puntos marcados antes de considerarlo terminado.")
    memory.log_evaluation(f"Calidad del proyecto {slug}", "Control de calidad",
                          score, feedback)
    if score < 0.8:
        failing = ", ".join(c["check"] for c in checks if not c["ok"])
        memory.add_learning(
            f"Al evaluar '{slug}' obtuvo {score}. Puntos débiles: {failing}. "
            "Antes de entregar un proyecto, verificar siempre esos puntos.",
            source="quality")
    return {"project": slug, "score": score, "passed": passed,
            "total": len(checks), "checks": checks, "feedback": feedback}


def evaluate_code(code: str) -> dict:
    issues = []
    try:
        ast.parse(code)
    except SyntaxError as exc:
        issues.append(f"sintaxis línea {exc.lineno}: {exc.msg}")
    if len(code) > 20000:
        issues.append("código demasiado largo: conviene dividirlo en funciones")
    if "eval(" in code or "exec(" in code:
        issues.append("uso de eval/exec: riesgo de seguridad")
    score = max(0.1, 1.0 - 0.25 * len(issues))
    return {"score": round(score, 3), "issues": issues}


def _tool_quality(args):
    return json.dumps(run_project_tests(args["project"]), ensure_ascii=False, indent=2)


def _tool_eval_code(args):
    return json.dumps(evaluate_code(args["code"]), ensure_ascii=False)


registry.register("run_quality_tests",
                  "Ejecuta la batería de pruebas de un proyecto y devuelve su puntuación.",
                  {"project": "string"}, _tool_quality)
registry.register("evaluate_code", "Evalúa un fragmento de código.",
                  {"code": "string"}, _tool_eval_code)