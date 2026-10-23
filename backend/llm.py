"""Conversación con el modelo de lenguaje. Si no hay modelo, motor offline determinista."""
import json
import re

import httpx

from .config import settings


class LLMError(RuntimeError):
    pass


class LLMClient:
    """Cliente compatible con OpenAI (Ollama, LM Studio, vLLM, APIs remotas)."""

    def __init__(self):
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model
        self.headers = {"Authorization": f"Bearer {settings.llm_api_key}",
                        "Content-Type": "application/json"}

    def available(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/models", headers=self.headers, timeout=4)
            return r.status_code == 200
        except Exception:
            return False

    def chat(self, messages: list, temperature: float = 0.35, max_tokens: int = 4096) -> str:
        payload = {"model": self.model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens}
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", headers=self.headers,
                           json=payload, timeout=settings.llm_timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMError(f"Fallo al consultar el modelo: {exc}") from exc


class OfflineLLM:
    """Motor local que sí ejecuta acciones reales cuando no hay modelo disponible."""

    def chat(self, messages: list, **_) -> str:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if messages and messages[-1]["role"] == "tool":
            return json.dumps({"thought": "Ejecuté la herramienta solicitada.",
                               "actions": [],
                               "reply": "Acción completada. Revisa el registro de actividad para el detalle."},
                              ensure_ascii=False)
        low = user.lower()
        actions = []
        if any(k in low for k in ("recuerda", "memoriza", "remember")):
            actions.append({"tool": "remember", "args": {"content": user, "kind": "instruction",
                                                        "importance": 0.8}})
        if "informe" in low or "reporte" in low:
            style = "empresarial" if "empresa" in low or "negocio" in low else "universitario"
            actions.append({"tool": "build_report",
                            "args": {"title": user[:70], "content": user, "style": style}})
        if "crea el archivo" in low or "crear archivo" in low or "create file" in low:
            m = re.search(r"(?:archivo|file)\s+([\w./\\-]+\.\w+)", user, re.I)
            if m:
                actions.append({"tool": "write_file",
                                "args": {"path": m.group(1), "content": user}})
        if "lista" in low or "ver archivos" in low:
            actions.append({"tool": "list_files", "args": {"path": "."}})
        if "busca" in low or "buscar" in low:
            m = re.search(r"(?:busca|buscar|search)\s+(.{2,60})", user, re.I)
            if m:
                actions.append({"tool": "search_text", "args": {"query": m.group(1).strip()}})
        if actions:
            return json.dumps({"thought": "Interpreté la orden en modo offline.",
                               "actions": actions,
                               "reply": "Ejecutando la solicitud en modo offline."}, ensure_ascii=False)
        return json.dumps({
            "thought": "Modo offline activo.",
            "actions": [{"tool": "remember", "args": {"content": user, "kind": "request",
                                                     "importance": 0.6}}],
            "reply": ("Modo offline: la petición quedó registrada en memoria permanente. "
                      "Conecta un modelo en .env (Ollama) para razonamiento completo, "
                      "pero las herramientas de archivos, informes y memoria ya funcionan.")},
            ensure_ascii=False)


llm = LLMClient()
offline_llm = OfflineLLM()


def get_engine():
    return llm if llm.available() else offline_llm


def parse_agent_output(text: str) -> dict:
    """Extrae el JSON de protocolo {thought, actions, reply} aunque venga en bloque de código."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            return {"thought": str(data.get("thought", "")),
                    "actions": [a for a in data.get("actions", []) if isinstance(a, dict)],
                    "reply": str(data.get("reply", ""))}
        except json.JSONDecodeError:
            pass
    return {"thought": "", "actions": [], "reply": text}