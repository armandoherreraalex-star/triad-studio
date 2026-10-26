"""Cola de tareas en segundo plano: progreso en vivo, reintentos y restauración."""
import json
import queue
import threading
import time
import uuid
from datetime import datetime, timezone

from .config import DATA_DIR

CHECKPOINTS = DATA_DIR / "task_checkpoints.json"


class TaskCancelled(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TaskQueue:
    def __init__(self, workers: int = 2):
        self.tasks: dict = {}
        self._fns: dict = {}
        self._lock = threading.Lock()
        self._q: queue.Queue = queue.Queue()
        self._load()
        for i in range(workers):
            threading.Thread(target=self._worker, name=f"triad-worker-{i}",
                             daemon=True).start()

    def submit(self, title: str, agent: str, fn, retries: int = 2) -> dict:
        tid = uuid.uuid4().hex[:10]
        task = {"id": tid, "title": str(title)[:200], "agent": agent,
                "status": "pending", "progress": 0, "log": [], "retries": 0,
                "result": "", "created": _now(), "updated": _now()}
        with self._lock:
            self.tasks[tid] = task
            self._fns[tid] = (fn, retries)
            self._save()
        self._q.put(tid)
        return dict(task)

    def list(self) -> list:
        with self._lock:
            return sorted(self.tasks.values(),
                          key=lambda t: t["created"], reverse=True)[:40]

    def get(self, tid: str):
        with self._lock:
            t = self.tasks.get(tid)
            return dict(t) if t else None

    def cancel(self, tid: str):
        with self._lock:
            t = self.tasks.get(tid)
            if t and t["status"] in ("pending", "running", "retrying"):
                t["status"] = "cancelled"
                t["updated"] = _now()
                self._save()
            return dict(t) if t else None

    def _report(self, tid: str, progress, text=None) -> None:
        task = self.tasks.get(tid)
        if not task:
            raise TaskCancelled()
        if task["status"] == "cancelled":
            raise TaskCancelled()
        task["progress"] = max(0, min(100, int(progress)))
        if text:
            task["log"].append({"t": _now(), "text": str(text)[:400]})
            task["log"] = task["log"][-80:]
        task["updated"] = _now()
        self._save()

    def _worker(self) -> None:
        while True:
            tid = self._q.get()
            with self._lock:
                fn, retries = self._fns.pop(tid, (None, 0))
            if fn is None:
                continue
            task = self.tasks.get(tid)
            if not task:
                continue
            attempt = 0
            while True:
                try:
                    task["status"] = "running"
                    task["updated"] = _now()
                    result = fn(lambda p, text=None: self._report(tid, p, text))
                    task["result"] = str(result)[:4000]
                    task["progress"] = 100
                    task["status"] = "done"
                    break
                except TaskCancelled:
                    task["status"] = "cancelled"
                    break
                except Exception as exc:
                    attempt += 1
                    task["retries"] = attempt
                    task["updated"] = _now()
                    task["log"].append(
                        {"t": _now(), "text": f"intento {attempt} fallido: {exc}"})
                    if attempt > retries:
                        task["status"] = "error"
                        task["result"] = f"{type(exc).__name__}: {exc}"
                        break
                    task["status"] = "retrying"
                    time.sleep(min(2 ** attempt, 20))
            self._save()

    def _save(self) -> None:
        try:
            CHECKPOINTS.write_text(json.dumps(self.tasks, ensure_ascii=False),
                                   encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        if not CHECKPOINTS.exists():
            return
        try:
            self.tasks = json.loads(CHECKPOINTS.read_text(encoding="utf-8"))
            for t in self.tasks.values():
                if t.get("status") in ("pending", "running", "retrying"):
                    t["status"] = "interrupted"
        except Exception:
            self.tasks = {}


task_queue = TaskQueue()


def submit_agent_task(title: str, agent_name: str = "", context: str = "") -> dict:
    """Crea un trabajo en segundo plano que las programadoras ejecutan solas."""
    def job(report):
        from .agents import AGENTS, AgentRuntime
        from .orchestrator import orchestrator
        from .self_improve import improver
        state = {"n": 0}

        def emit(name, kind, text):
            state["n"] += 1
            report(min(95, state["n"] * 8), f"{name} [{kind}] {text}")

        if agent_name and agent_name in AGENTS:
            out = AgentRuntime(AGENTS[agent_name]).run(title, emit=emit, context=context)
        else:
            out = orchestrator.handle(title, emit=emit)
        improver.after_run(title, agent_name or "Director",
                           out.get("status", "done"), out.get("steps", 1))
        return out.get("reply", "Tarea completada.")

    return task_queue.submit(title, agent_name or "Director", job)


def _tool_submit(args):
    return json.dumps(submit_agent_task(args.get("title", "tarea sin título"),
                                        args.get("agent", ""),
                                        args.get("context", "")),
                      ensure_ascii=False)


def _tool_list(args):
    return json.dumps(task_queue.list(), ensure_ascii=False)


def _tool_status(args):
    t = task_queue.get(args["id"])
    return json.dumps(t or {"error": "tarea no encontrada"}, ensure_ascii=False)


def _tool_cancel(args):
    return json.dumps(task_queue.cancel(args["id"]) or {"error": "no existe"},
                      ensure_ascii=False)


from .tools import registry  # noqa: E402

registry.register("submit_task",
                  "Lanza una tarea larga en segundo plano con progreso y reintentos.",
                  {"title": "string", "agent": "string opcional", "context": "string"},
                  _tool_submit)
registry.register("list_tasks", "Lista las tareas y su progreso.", {}, _tool_list)
registry.register("task_status", "Consulta el estado de una tarea.", {"id": "string"},
                  _tool_status)
registry.register("cancel_task", "Cancela una tarea en curso.", {"id": "string"},
                  _tool_cancel)