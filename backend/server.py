
"""Servidor FastAPI: panel web, API REST, proyectos, agentes, voz y eventos."""

import asyncio
from .r2_backup import backup_all
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.config import BASE_DIR, FRONTEND_DIR
from backend import voice as voice_engine
from backend.agent_factory import (
    create_agent as _create_agent,
    load_custom_agents,
    list_agents,
)
from backend.agents import AGENTS as _ALL_AGENTS, AgentRuntime
from backend.memory import memory
from backend.orchestrator import orchestrator
from backend.projects import project_manager
from backend.quality import run_project_tests
from backend.self_improve import improver
from backend.task_queue import task_queue, submit_agent_task
from backend.templates import create_project, list_templates, template_info
from backend.tools import load_custom_tools, registry


app = FastAPI(title="TRIAD STUDIO", version="3.0")

load_custom_tools()
load_custom_agents()

ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

LOOP: Optional[asyncio.AbstractEventLoop] = None
clients: set = set()


# ================= EVENTOS EN TIEMPO REAL =================

def emit(agent: str, kind: str, text: str) -> None:
    if LOOP is None:
        return
    LOOP.call_soon_threadsafe(
        _broadcast,
        {"agent": agent, "type": kind, "text": text},
    )


def _broadcast(event: dict) -> None:
    for ws in list(clients):
        asyncio.create_task(_safe_send(ws, event))


async def _safe_send(ws: WebSocket, event: dict) -> None:
    try:
        await ws.send_json(event)
    except Exception:
        clients.discard(ws)



@app.on_event("startup")
async def _startup() -> None:
    global LOOP
    LOOP = asyncio.get_running_loop()
    asyncio.create_task(_backup_loop())


async def _backup_loop():
    import logging

    while True:
        try:
            await asyncio.to_thread(backup_all, memory.conn)
            logging.info("Respaldo automático de TRIAD completado.")
        except Exception:
            logging.exception("Error al respaldar en Cloudflare R2")

        await asyncio.sleep(300)  # 5 minutos


# ================= PANEL Y ESTADO =================

@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))



@app.get("/api/state")
def state():
    import logging

    logger = logging.getLogger(__name__)

    # Mantener la estructura original y permitir que el panel
    # siga funcionando si falla alguno de sus componentes.
    result = {
        "engine": "offline",
        "stats": {
            "memories": 0,
            "messages": 0,
            "tools": 0,
            "evaluations": 0,
            "learnings": 0,
            "avg_score": 0.0,
        },
        "agents": [],
        "tools": [],
        "learnings": [],
        "evolution": {
            "samples": 0,
            "average": 0.0,
            "trend": 0.0,
            "learnings": 0,
        },
        "recent": [],
    }

    # Estado del motor
    try:
        result["engine"] = (
            "online" if orchestrator.engine_online else "offline"
        )
    except Exception:
        logger.exception("Error obteniendo estado del motor")

  
    # Estadísticas de memoria
    try:
        result["stats"] = memory.stats()
    except Exception:
        logger.exception("Error obteniendo estadísticas de memoria")
        result["stats"] = {
            "memories": 0,
            "messages": 0,
            "tools": 0,
            "evaluations": 0,
            "learnings": 0,
            "avg_score": 0.0,
        }

    # Agentes: conservar los existentes y tolerar atributos ausentes
    try:
        agents = []

        for key, agent in _ALL_AGENTS.items():
            try:
                agents.append({
                    "name": getattr(agent, "name", key),
                    "role": getattr(agent, "role", "Sin rol"),
                    "specialty": getattr(agent, "specialty", ""),
                    "color": getattr(agent, "color", "#64748b"),
                    "voice": getattr(agent, "voice", ""),
                })
            except Exception:
                logger.exception(
                    "Error obteniendo datos del agente %s", key
                )

        result["agents"] = agents

    except Exception:
        logger.exception("Error obteniendo agentes")
        result["agents"] = []

    # Herramientas registradas
    try:
        result["tools"] = registry.list()
    except Exception:
        logger.exception("Error obteniendo herramientas")

    # Aprendizajes
    try:
        result["learnings"] = memory.list_learnings(10)
    except Exception:
        logger.exception("Error obteniendo aprendizajes")

    # Evolución del sistema
    try:
        result["evolution"] = improver.evolution_report()
    except Exception:
        logger.exception("Error obteniendo informe de evolución")

    # Conversaciones recientes
    try:
        result["recent"] = memory.recent_messages("default", 12)
    except Exception:
        logger.exception("Error obteniendo conversaciones recientes")

    return result


# ================= CHAT =================

class ChatIn(BaseModel):
    message: str
    agent: Optional[str] = None
    session: str = "default"


@app.post("/api/chat")
def chat(payload: ChatIn):
    if not payload.message.strip():
        return JSONResponse(
            {"error": "Mensaje vacío."},
            status_code=400,
        )

    if payload.agent and payload.agent in _ALL_AGENTS:
        out = AgentRuntime(_ALL_AGENTS[payload.agent]).run(
            payload.message,
            session=payload.session,
            emit=emit,
        )
        improver.after_run(
            payload.message,
            payload.agent,
            out["status"],
            out["steps"],
        )
        return {
            "reply": out["reply"],
            "results": [out],
            "evaluation": improver.evolution_report(),
        }

    return orchestrator.handle(
        payload.message,
        session=payload.session,
        emit=emit,
    )


# ================= MEMORIA =================

class MemoryIn(BaseModel):
    content: str
    kind: str = "general"
    tags: str = ""
    importance: float = 0.6


@app.post("/api/memory")
def add_memory(payload: MemoryIn):
    mid = memory.store(
        payload.content,
        payload.kind,
        payload.tags,
        payload.importance,
    )
    return {"ok": True, "id": mid}


@app.get("/api/memory")
def list_memory(q: str = ""):
    if q:
        return {"items": memory.search(q, limit=20)}
    return {"items": memory.recent_memories(30)}


# ================= HERRAMIENTAS PERSONALIZADAS =================

class ToolIn(BaseModel):
    name: str
    description: str
    code: str


@app.post("/api/tools")
def create_tool(payload: ToolIn):
    return improver.propose_tool(
        payload.name,
        payload.description,
        payload.code,
    )


@app.post("/api/tools/generate")
def generate_tool(spec: str):
    code = f'''"""Herramienta generada por Toolsmith."""
TOOL = {{
    "name": "custom_{spec[:24].lower().replace(' ', '_')}",
    "description": {spec!r},
    "parameters": {{}},
    "run": lambda args: "Herramienta base creada a partir de: {spec}",
}}


def test():
    assert callable(TOOL["run"])
'''
    return improver.propose_tool(spec[:24], spec, code)


@app.get("/api/evolution")
def evolution():
    return improver.evolution_report()


# ================= FASE 2: FÁBRICA DE APLICACIONES =================

class ProjectCreate(BaseModel):
    template: str
    name: str
    vars: dict = Field(default_factory=dict)


class ProjectAction(BaseModel):
    project: str
    command: str = "serve"


@app.get("/api/templates")
def api_templates():
    return {"templates": list_templates()}


@app.get("/api/templates/{template}")
def api_template_info(template: str):
    try:
        return template_info(template)
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


@app.get("/api/projects")
def api_projects():
    return {"projects": project_manager.list()}


@app.post("/api/projects/create")
def api_create_project(payload: ProjectCreate):
    try:
        meta = create_project(
            payload.template,
            payload.name,
            payload.vars,
        )
        emit(
            "Director",
            "plan",
            f"Proyecto '{payload.name}' creado desde {payload.template}",
        )
        return {"ok": True, "project": meta}
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


@app.post("/api/projects/start")
def api_start_project(payload: ProjectAction):
    try:
        result = project_manager.start(
            payload.project,
            payload.command,
        )
        emit("Eris", "tool", f"Proyecto {payload.project} iniciado")
        return {"ok": True, "result": result}
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


@app.post("/api/projects/stop")
def api_stop_project(payload: ProjectAction):
    try:
        result = project_manager.stop(payload.project)
        return {"ok": True, "result": result}
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


@app.post("/api/projects/install")
def api_install_project(payload: ProjectAction):
    try:
        output = project_manager.install(payload.project)
        return {"ok": True, "output": output}
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


@app.get("/api/projects/export")
def api_export_project(project: str):
    try:
        path = project_manager.export(project)
        return {"ok": True, "zip": path}
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


@app.get("/api/projects/log")
def api_project_log(project: str, lines: int = 40):
    try:
        log = project_manager.log_tail(project, lines)
        return {"ok": True, "log": log}
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


# ================= FASE 3: TAREAS Y AGENTES =================

@app.get("/api/tasks")
def api_tasks():
    return {"tasks": task_queue.list()}


class TaskIn(BaseModel):
    title: str
    agent: Optional[str] = None
    context: str = ""


@app.post("/api/tasks")
def api_create_task(payload: TaskIn):
    task = submit_agent_task(
        payload.title,
        payload.agent or "",
        payload.context,
    )
    emit("Director", "plan", f"Tarea en cola: {payload.title[:100]}")
    return {"ok": True, "task": task}


@app.get("/api/tasks/{tid}")
def api_task(tid: str):
    task = task_queue.get(tid)
    if task is None:
        return JSONResponse(
            {"error": "No existe esa tarea."},
            status_code=404,
        )
    return task


@app.post("/api/tasks/{tid}/cancel")
def api_cancel_task(tid: str):
    return {"ok": True, "task": task_queue.cancel(tid)}


@app.get("/api/agents")
def api_agents():
    return {"agents": list_agents()}


class AgentCreate(BaseModel):
    name: str
    role: str = "Especialista"
    specialty: str = "General"
    description: str
    tools: list = Field(default_factory=list)
    pitch: float = 1.0
    rate: float = 1.0


@app.post("/api/agents")
def api_create_agent(payload: AgentCreate):
    try:
        result = _create_agent(
            payload.name,
            payload.role,
            payload.specialty,
            payload.description,
            tools=payload.tools,
            pitch=payload.pitch,
            rate=payload.rate,
        )
        emit("Director", "plan", f"Nuevo agente: {payload.name}")
        return result
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


# ================= PRUEBAS DE CALIDAD =================

class QualityIn(BaseModel):
    project: str


@app.post("/api/quality/run")
def api_quality(payload: QualityIn):
    try:
        result = run_project_tests(payload.project)
        emit(
            "Director",
            "score",
            f"Calidad de {payload.project}: {result.get('score', 0)}",
        )
        return result
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


# ================= VOZ =================

class VoiceIn(BaseModel):
    agent: str
    text: str


@app.post("/api/voice")
def api_voice(payload: VoiceIn):
    if not voice_engine.available():
        return JSONResponse(
            {"error": "edge-tts no instalado"},
            status_code=503,
        )

    try:
        data = voice_engine.synth(payload.agent, payload.text)
        return Response(content=data, media_type="audio/mpeg")
    except Exception as exc:
        return JSONResponse(
            {"error": str(exc)},
            status_code=500,
        )


@app.get("/api/voice/status")
def api_voice_status():
    voices = {
        agent: config["voice"]
        for agent, config in voice_engine.CHARACTERS.items()
    }
    return {"ok": voice_engine.available(), "voices": voices}



# ================= COPIAS DE SEGURIDAD =================

@app.post("/api/backup")
def api_backup():
    try:
        backup_all(memory.conn)
        return {
            "ok": True,
            "result": "Copia ZIP guardada en Cloudflare R2"
        }
    except Exception as exc:
        import logging
        logging.exception("Error al crear la copia de seguridad")
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=500,
        )


# ================= WEBSOCKET =================

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
    except Exception:
        clients.discard(ws)
