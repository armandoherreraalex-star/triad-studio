"""Director: interpreta el objetivo, reparte el trabajo entre las tres y sintetiza."""
import re
from typing import Callable, Optional

from .agents import AGENTS, AgentRuntime
from .llm import get_engine
from .memory import memory
from .self_improve import improver

ROUTE = {
    "Sylphiette": ["frontend", "interfaz", "ui", "ux", "css", "html", "react", "diseño",
                   "informe", "documento", "app móvil", "movil", "accesibilidad", "web",
                   "landing", "presentación", "logo"],
    "Roxy": ["backend", "api", "base de datos", "datos", "python", "algoritmo",
                      "inteligencia artificial", "ia ", "rag", "investig", "informe universitario",
                      "universidad", "sql", "arquitectura", "modelo", "seguridad", "análisis"],
    "Eris": ["automatiz", "script", "terminal", "ejecut", "devops", "docker",
                            "prueba", "test", "juego", "game", "rendimiento", "depur",
                            "error", "compilar", "sistema", "infraestructura", "bot"],
}


def classify(text: str) -> str:
    low = text.lower()
    scores = {name: sum(low.count(k) for k in keys) for name, keys in ROUTE.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Roxy"


def split_tasks(text: str) -> list:
    """Divide objetivos grandes en subtareas cuando el usuario enumera varias cosas."""
    lines = [l.strip() for l in re.split(r"[\n;]|(?=\d+\.\s)", text) if len(l.strip()) > 12]
    tasks = [l for l in lines if len(l) > 12][:6]
    return tasks if len(tasks) >= 2 else [text]


class Orchestrator:
    def __init__(self):
        self.runtimes = {name: AgentRuntime(agent) for name, agent in AGENTS.items()}
        self.engine_online = get_engine().__class__.__name__ == "LLMClient"

    def handle(self, message: str, session: str = "default",
               emit: Optional[Callable] = None) -> dict:
        emit = emit or (lambda *a: None)
        emit("Director", "status", "descomponiendo el objetivo")
        tasks = split_tasks(message)
        results, errors = [], 0
        for task in tasks:
            owner = classify(task)
            emit("Director", "plan", f"Asigno a {owner}: {task[:120]}")
            try:
                out = self.runtimes[owner].run(task, session=session, emit=emit,
                                               context=message[:600])
                results.append(out)
                errors += 1 if out["status"] != "done" else 0
            except Exception as exc:
                errors += 1
                results.append({"agent": owner, "reply": f"Error controlado: {exc}",
                                "steps": 0, "status": "error"})
                emit(owner, "error", str(exc)[:200])
        emit("Director", "status", "sintetizando resultados")
        final = self._synthesize(message, results)
        memory.store(f"Petición: {message[:200]} → respuesta generada por "
                     f"{', '.join(r['agent'] for r in results)}",
                     kind="session", tags="historial", importance=0.7)
        score = improver.after_run(message, "Director", "done" if not errors else "partial",
                                   sum(r.get("steps", 0) for r in results), errors)
        emit("Director", "score", f"Evaluación del ciclo: {score['score']:.2f} · {score['feedback']}")
        return {"reply": final, "results": results, "evaluation": score,
                "engine": "modelo conectado" if self.engine_online else "modo offline"}

    def _synthesize(self, message: str, results: list) -> str:
        if len(results) == 1:
            r = results[0]
            return f"[{r['agent']} · {AGENTS[r['agent']].specialty}]\n\n{r['reply']}"
        parts = [f"[{r['agent']} · {AGENTS[r['agent']].specialty}]\n{r['reply']}"
                 for r in results]
        header = (f"He coordinado {len(results)} especialistas para: "
                  f"«{message[:120]}». Resumen consolidado:\n")
        return header + "\n\n".join(parts)


orchestrator = Orchestrator()