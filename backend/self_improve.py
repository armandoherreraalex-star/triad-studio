"""Ciclo de auto-mejora: evalúa cada ejecución, extrae reglas y fabrica herramientas."""
import ast
import importlib.util
from datetime import datetime, timezone

from .config import CUSTOM_TOOLS_DIR
from .memory import memory
from .tools import load_custom_tools, registry


class SelfImprover:
    def after_run(self, task: str, agent: str, status: str, steps: int,
                  errors: int = 0) -> dict:
        score = 1.0
        if status == "step_limit":
            score -= 0.35
        score -= min(errors * 0.15, 0.5)
        score -= max(0, (steps - 2) * 0.05)
        score = max(0.1, min(1.0, score))
        feedback = ("Ejecución limpia." if score >= 0.75 else
                    "Revisar: reducir pasos o precisar la instrucción inicial.")
        memory.log_evaluation(task[:400], agent, score, feedback)
        if score < 0.8:
            memory.add_learning(
                f"Al obtener score {score:.2f} en '{task[:80]}', conviene dividir la tarea en "
                f"subtareas más pequeñas antes de ejecutar herramientas.", source="auto_eval")
        if errors:
            memory.add_learning(
                f"Se produjeron {errors} errores en '{task[:80]}': validar argumentos de "
                f"herramientas antes de ejecutarlas.", source="auto_eval")
        return {"score": score, "feedback": feedback}

    def propose_tool(self, name: str, description: str, code: str) -> dict:
        """Crea una herramienta nueva. Si falla su prueba, la retira automáticamente."""
        clean = "".join(ch for ch in name if ch.isalnum() or ch == "_").lower()
        if not clean:
            return {"ok": False, "error": "Nombre de herramienta inválido."}
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return {"ok": False, "error": f"Sintaxis inválida línea {exc.lineno}: {exc.msg}"}
        path = CUSTOM_TOOLS_DIR / f"{clean}.py"
        path.write_text(code, encoding="utf-8")
        try:
            spec = importlib.util.spec_from_file_location(f"custom_{clean}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            meta = getattr(module, "TOOL", None)
            if not meta or "run" not in meta:
                raise ValueError("El módulo debe definir TOOL con la clave 'run'.")
            test = getattr(module, "test", None)
            if test:
                test()
            registry.register(meta["name"], description or meta.get("description", ""),
                              meta.get("parameters", {}), meta["run"])
            memory.save_tool(clean, description, code)
            memory.add_learning(f"Herramienta '{clean}' creada y verificada con prueba automática.",
                                source="toolsmith")
            load_custom_tools()
            return {"ok": True, "tool": clean, "version": "activa"}
        except Exception as exc:
            path.unlink(missing_ok=True)
            memory.retire_tool(clean)
            memory.add_learning(f"La herramienta '{clean}' falló su prueba ({exc}) y fue retirada. "
                                f"Antes de crear herramientas, incluir una función test() que "
                                f"valide la lógica.", source="toolsmith")
            return {"ok": False, "error": str(exc), "rollback": True}

    def evolution_report(self) -> dict:
        evals = memory.conn.execute(
            "SELECT score, created_at FROM evaluations ORDER BY id DESC LIMIT 40").fetchall()
        scores = [e["score"] for e in evals]
        trend = 0.0
        if len(scores) >= 4:
            trend = round(sum(scores[:len(scores)//2]) / max(len(scores)//2, 1)
                          - sum(scores[len(scores)//2:]) / max(len(scores) - len(scores)//2, 1), 3)
        return {"samples": len(scores),
                "average": round(sum(scores) / len(scores), 3) if scores else 0.0,
                "trend": trend,
                "learnings": len(memory.list_learnings(50)),
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


improver = SelfImprover()