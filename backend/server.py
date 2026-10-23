"""Servidor FastAPI: panel web, API REST y eventos en tiempo real."""
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import FRONTEND_DIR
from .memory import memory
from .orchestrator import orchestrator
from .self_improve import improver
from .tools import load_custom_tools, registry

app = FastAPI(title="TRIAD STUDIO", version="1.0")

load_custom_tools()

LOOP: Optional[asyncio.AbstractEventLoop] = None
clients: set = set()


def emit(agent: str, kind: str, text: str) -> None:
    """Envía un evento al panel. Seguro desde hilos de trabajo."""
    if LOOP is None:
        return
    LOOP.call_soon_threadsafe(_broadcast, {"agent": agent, "type": kind, "text": text})


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
    LOOP = asyncio.get_event_loop()


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/state")
def state():
    return {
        "engine": "online" if orchestrator.engine_online else "offline",
        "stats": memory.stats(),
        "agents": [{"name": a.name, "role": a.role, "specialty": a.specialty,
                    "color": a.color} for a in
                   [__import__("backend.agents", fromlist=["AGENTS"]).AGENTS[n]
                    for n in ("Sylphiette", "Roxy Migurdia", "Eris Boreas Greyrat")]],
        "tools": registry.list(),
        "learnings": memory.list_learnings(10),
        "evolution": improver.evolution_report(),
        "recent": memory.recent_messages("default", 12),
    }


class ChatIn(BaseModel):
    message: str
    agent: Optional[str] = None
    session: str = "default"


@app.post("/api/chat")
def chat(payload: ChatIn):
    if not payload.message.strip():
        return JSONResponse({"error": "Mensaje vacío."}, status_code=400)
    if payload.agent:
        from .agents import AGENTS, AgentRuntime
        agent = AGENTS.get(payload.agent)
        if agent:
            out = AgentRuntime(agent).run(payload.message, session=payload.session, emit=emit)
            improver.after_run(payload.message, agent.name, out["status"], out["steps"])
            return {"reply": out["reply"], "results": [out],
                    "evaluation": improver.evolution_report()}
    out = orchestrator.handle(payload.message, session=payload.session, emit=emit)
    return out


class MemoryIn(BaseModel):
    content: str
    kind: str = "general"
    tags: str = ""
    importance: float = 0.6


@app.post("/api/memory")
def add_memory(payload: MemoryIn):
    mid = memory.store(payload.content, payload.kind, payload.tags, payload.importance)
    return {"ok": True, "id": mid}


@app.get("/api/memory")
def list_memory(q: str = ""):
    if q:
        return {"items": memory.search(q, limit=20)}
    return {"items": memory.recent_memories(30)}


class ToolIn(BaseModel):
    name: str
    description: str
    code: str


@app.post("/api/tools")
def create_tool(payload: ToolIn):
    return improver.propose_tool(payload.name, payload.description, payload.code)


@app.post("/api/tools/generate")
def generate_tool(spec: str):
    """El propio agente redacta una herramienta a partir de una especificación."""
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