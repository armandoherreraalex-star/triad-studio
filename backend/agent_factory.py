"""Fábrica de agentes: crea especialistas nuevos con perfil, herramientas y persistencia."""
import json
import re

from .agents import AGENTS, Agent
from .config import CUSTOM_TOOLS_DIR
from .memory import memory
from .tools import registry

AGENTS_DIR = CUSTOM_TOOLS_DIR / "agents"
AGENTS_DIR.mkdir(parents=True, exist_ok=True)


def _clean(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ ]", "", (name or "")).strip()[:32]


def create_agent(name: str, role: str, specialty: str, description: str,
                 tools=None, pitch: float = 1.0, rate: float = 1.0) -> dict:
    clean = _clean(name)
    if len(clean) < 2:
        raise ValueError("Nombre de agente demasiado corto.")
    if clean in AGENTS:
        raise ValueError(f"Ya existe un agente llamado '{clean}'.")
    if clean in ("Director", "Sistema"):
        raise ValueError("Ese nombre está reservado.")
    if len((description or "").strip()) < 15:
        raise ValueError("La descripción del agente debe tener al menos 15 caracteres.")

    available = {t["name"] for t in registry.list()}
    chosen = [t for t in (tools or []) if t in available]
    if not chosen:
        chosen = ["read_file", "write_file", "list_files", "search_text",
                  "remember", "recall"]

    prompt = (f"Eres {clean}, {role} dentro del estudio TRIAD. "
              f"Especialidad: {specialty}. {description.strip()} "
              f"Responde siempre en el idioma del usuario. "
              "Entrega trabajo terminado, verificable y con errores corregidos.")

    agent = Agent(
        name=clean, role=role, specialty=specialty or "General",
        color="#c084fc",
        voice={"pitch": float(pitch), "rate": float(rate),
               "greeting": f"{clean}, en línea."},
        system_prompt=prompt,
        tools=chosen)

    path = AGENTS_DIR / (clean.lower().replace(" ", "_") + ".json")
    try:
        path.write_text(json.dumps({
            "name": clean, "role": role, "specialty": specialty,
            "description": description, "tools": chosen,
            "voice": agent.voice, "prompt": prompt,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        path.unlink(missing_ok=True)
        raise

    AGENTS[clean] = agent
    memory.store(f"Agente creado: {clean} ({role}) con herramientas: {', '.join(chosen)}",
                 kind="agent", tags="factory", importance=0.85)
    memory.add_learning(
        f"El agente '{clean}' resuelve tareas de: {specialty}. "
        f"Conviene asignarle ese tipo de trabajo.", source="agent_factory")
    return {"ok": True, "agent": clean, "tools": chosen}


def load_custom_agents() -> int:
    loaded = 0
    for file in sorted(AGENTS_DIR.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            name = data["name"]
            if name in AGENTS:
                continue
            AGENTS[name] = Agent(
                name=name, role=data.get("role", "Especialista"),
                specialty=data.get("specialty", "General"),
                color="#c084fc",
                voice=data.get("voice", {"pitch": 1.0, "rate": 1.0,
                                         "greeting": f"{name}, en línea."}),
                system_prompt=data.get("prompt", f"Eres {name}, agente especializado."),
                tools=data.get("tools", []))
            loaded += 1
        except Exception:
            memory.add_learning(
                f"El perfil de agente '{file.name}' está dañado y fue ignorado. "
                "Validar el JSON antes de guardarlo.", source="agent_factory")
    return loaded


def list_agents() -> list:
    return [{"name": a.name, "role": a.role, "specialty": a.specialty,
             "color": a.color, "voice": a.voice, "tools": a.tools,
             "custom": a.color == "#c084fc"} for a in AGENTS.values()]


def _tool_create(args):
    try:
        return json.dumps(create_agent(
            args.get("name", ""), args.get("role", "Especialista"),
            args.get("specialty", "General"), args.get("description", ""),
            tools=args.get("tools"), pitch=args.get("pitch", 1.0),
            rate=args.get("rate", 1.0)), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


def _tool_list(args):
    return json.dumps(list_agents(), ensure_ascii=False)


registry.register("create_agent",
                  "Crea un agente especializado nuevo con perfil, voz y herramientas.",
                  {"name": "string", "role": "string", "specialty": "string",
                   "description": "string", "tools": "lista", "pitch": "float",
                   "rate": "float"}, _tool_create)
registry.register("list_agents", "Lista todos los agentes del estudio.", {}, _tool_list)