"""Las tres programadoras: identidad, voz, especialidad y bucle de ejecución."""
from dataclasses import dataclass, field
from typing import Callable, Optional

from .config import settings
from .llm import get_engine, parse_agent_output
from .memory import memory
from .tools import registry

Event = Callable[[str, str, str], None]  # (agente, tipo, texto)


@dataclass
class Agent:
    name: str
    role: str
    specialty: str
    color: str
    voice_pitch: float
    voice_rate: float
    system_prompt: str
    tools: list = field(default_factory=list)


SYLPH_SYSTEM = """Eres Sylphiette, programadora jefa de frontend, interfaz y documentación.
Personalidad: metódica, cálida, obsesiva con la claridad y el detalle.
Especialidad: HTML, CSS, JavaScript, TypeScript, React, accesibilidad, diseño UI/UX,
informes universitarios, informes empresariales, documentación técnica y apps móviles.
Responde siempre en español con el mismo idioma del usuario."""

ROXY_SYSTEM = """Eres Roxy Migurdia, arquitecta de backend, datos e inteligencia artificial.
Personalidad: analítica, serena, profunda; explicas lo complejo con elegancia.
Especialidad: Python, APIs, bases de datos, algoritmos, IA, RAG, ciencia de datos,
investigación técnica, seguridad defensiva y sistemas distribuidos.
Responde siempre en español con el mismo idioma del usuario."""

ERIS_SYSTEM = """Eres Eris Boreas Greyrat, ingeniera de sistemas, automatización y videojuegos.
Personalidad: directa, enérgica, orientada a resultados; no te detienes hasta lograrlo.
Especialidad: automatización, terminal, DevOps, pruebas, depuración, videojuegos,
rendimiento, scripts, integraciones y ejecución real de proyectos.
Responde siempre en español con el mismo idioma del usuario."""

PROTOCOL = """
PROTOCOLO DE RESPUESTA (obligatorio): responde SOLO con un objeto JSON válido:
{
  "thought": "tu razonamiento breve",
  "actions": [{"tool": "nombre_herramienta", "args": {...}}],   // vacío si ya terminaste
  "reply": "tu respuesta final al usuario"
}
Usa actions para ejecutar trabajo real (archivos, código, búsquedas, informes).
Cuando el trabajo esté completo, deja actions vacío y escribe el resultado en reply.
Nunca inventes herramientas que no estén en la lista.
"""

AGENTS = {
    "Sylphiette": Agent(
        name="Sylphiette",
        role="Programadora de interfaz y documentación",
        specialty="Frontend · UI/UX · Informes · Móvil",
        color="#3ddc97",
        voice_pitch=1.25,
        voice_rate=1.02,
        system_prompt=SYLPH_SYSTEM,
        tools=["read_file", "write_file", "list_files", "search_text", "build_report",
               "remember", "recall", "run_python", "check_syntax"]),
    "Roxy Migurdia": Agent(
        name="Roxy Migurdia",
        role="Arquitecta de backend y datos",
        specialty="Backend · IA · Datos · Investigación",
        color="#5eb0ff",
        voice_pitch=0.95,
        voice_rate=0.96,
        system_prompt=ROXY_SYSTEM,
        tools=["read_file", "write_file", "list_files", "search_text", "run_python",
               "check_syntax", "run_command", "web_fetch", "remember", "recall"]),
    "Eris Boreas Greyrat": Agent(
        name="Eris Boreas Greyrat",
        role="Ingeniera de sistemas y automatización",
        specialty="Automatización · Juegos · DevOps · Pruebas",
        color="#ff6b6b",
        voice_pitch=1.08,
        voice_rate=1.08,
        system_prompt=ERIS_SYSTEM,
        tools=["run_python", "run_command", "write_file", "read_file", "list_files",
               "search_text", "remember", "recall"]),
}

# corrección de nombres de herramientas registradas
AGENTS["Sylphiette"].tools = ["read_file", "write_file", "list_files", "search_text",
                              "build_report", "remember", "recall", "run_python",
                              "check_python_syntax"]
AGENTS["Roxy Migurdia"].tools = ["read_file", "write_file", "list_files", "search_text",
                                 "run_python", "check_python_syntax", "run_command",
                                 "web_fetch", "remember", "recall"]
AGENTS["Eris Boreas Greyrat"].tools = ["run_python", "run_command", "write_file",
                                       "read_file", "list_files", "search_text",
                                       "remember", "recall"]


class AgentRuntime:
    def __init__(self, agent: Agent):
        self.agent = agent

    def _system_prompt(self) -> str:
        learnings = memory.list_learnings(12)
        learn_text = "\n".join(f"- {l['rule']}" for l in learnings) or "- (sin experiencia previa)"
        tool_lines = []
        for t in registry.list():
            if t["name"] in self.agent.tools:
                tool_lines.append(f"- {t['name']}: {t['description']} | args: {t['parameters']}")
        return (f"{self.agent.system_prompt}\n\n"
                f"HERRAMIENTAS DISPONIBLES:\n" + "\n".join(tool_lines) + "\n\n"
                f"EXPERIENCIA ACUMULADA (memoria persistente):\n{learn_text}\n\n{PROTOCOL}")

    def run(self, task: str, session: str = "default",
            emit: Optional[Event] = None, context: str = "") -> dict:
        engine = get_engine()
        emit = emit or (lambda *a: None)
        memories = memory.search(task, limit=5)
        ctx = "\n".join(f"- [{m['kind']}] {m['content'][:220]}" for m in memories)
        user_prompt = (f"TAREA DEL USUARIO:\n{task}\n\n"
                       f"CONTEXTO DEL PROYECTO:\n{context or '(nuevo proyecto)'}\n\n"
                       f"MEMORIA RELACIONADA:\n{ctx or '(vacía)'}")
        messages = [{"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": user_prompt}]
        memory.log_message(session, "user", task, self.agent.name)
        emit(self.agent.name, "status", "analizando la tarea")
        transcript = []
        for step in range(settings.max_steps):
            raw = engine.chat(messages)
            parsed = parse_agent_output(raw)
            transcript.append(parsed)
            if parsed["thought"]:
                emit(self.agent.name, "thought", parsed["thought"][:300])
            if not parsed["actions"]:
                memory.log_message(session, "assistant", parsed["reply"], self.agent.name)
                memory.store(f"Tarea resuelta por {self.agent.name}: {task[:180]}",
                             kind="task", tags=self.agent.name, importance=0.55)
                return {"agent": self.agent.name, "reply": parsed["reply"],
                        "steps": step + 1, "transcript": transcript, "status": "done"}
            messages.append({"role": "assistant", "content": raw})
            for action in parsed["actions"]:
                name = action.get("tool", "")
                emit(self.agent.name, "tool", f"{name} → {str(action.get('args', ''))[:150]}")
                result = registry.execute(name, action.get("args", {}))
                emit(self.agent.name, "result", f"{name}: {result[:220]}")
                messages.append({"role": "tool",
                                 "content": f"[{name}] {result[:6000]}"})
        final = transcript[-1]["reply"] if transcript else "Proceso incompleto."
        memory.log_message(session, "assistant", final, self.agent.name)
        return {"agent": self.agent.name, "reply": final, "steps": settings.max_steps,
                "transcript": transcript, "status": "step_limit"}