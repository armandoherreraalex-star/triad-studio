"""Memoria persistente: conversaciones, proyectos, aprendizajes y herramientas."""
import re
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from .config import DATA_DIR

DB_PATH = DATA_DIR / "triad_memory.db"
_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL DEFAULT 'general',
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    importance REAL NOT NULL DEFAULT 0.5,
    created_at TEXT NOT NULL,
    last_access TEXT NOT NULL,
    accesses INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    role TEXT NOT NULL,
    agent TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    agent TEXT NOT NULL DEFAULT '',
    score REAL NOT NULL,
    feedback TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'auto',
    created_at TEXT NOT NULL
);
"""

_STOP = {"que", "para", "como", "con", "una", "los", "las", "del", "por", "the",
         "and", "for", "with", "this", "that", "from"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9_áéíóúñü]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOP}


class Memory:
    """Almacenamiento estructurado con búsqueda por relevancia."""

    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # ---------- memorias ----------
    def store(self, content: str, kind: str = "general", tags: str = "",
              importance: float = 0.5) -> int:
        with _lock:
            cur = self.conn.execute(
                "INSERT INTO memories (kind, content, tags, importance, created_at, last_access)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (kind, content, tags, float(importance), _now(), _now()))
            self.conn.commit()
            return cur.lastrowid

    def search(self, query: str, kind: Optional[str] = None, limit: int = 8) -> list:
        q = _tokens(query)
        sql = "SELECT * FROM memories" + (" WHERE kind = ?" if kind else "")
        rows = self.conn.execute(sql, (kind,) if kind else ()).fetchall()
        scored = []
        for row in rows:
            tokens = _tokens(row["content"] + " " + row["tags"])
            overlap = len(q & tokens)
            score = (overlap / max(len(q), 1)) + row["importance"] * 0.3 + min(row["accesses"], 5) * 0.02
            if overlap or not q:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, row in scored[:limit]:
            with _lock:
                self.conn.execute(
                    "UPDATE memories SET accesses = accesses + 1, last_access = ? WHERE id = ?",
                    (_now(), row["id"]))
                self.conn.commit()
            out.append({"id": row["id"], "kind": row["kind"], "content": row["content"],
                        "tags": row["tags"], "importance": row["importance"],
                        "score": round(score, 3)})
        return out

    def recent_memories(self, limit: int = 12) -> list:
        rows = self.conn.execute(
            "SELECT * FROM memories ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- conversación ----------
    def log_message(self, session: str, role: str, content: str, agent: str = "") -> None:
        with _lock:
            self.conn.execute(
                "INSERT INTO messages (session, role, agent, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (session, role, agent, content, _now()))
            self.conn.commit()

    def recent_messages(self, session: str, limit: int = 20) -> list:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE session = ? ORDER BY id DESC LIMIT ?",
            (session, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ---------- herramientas ----------
    def save_tool(self, name: str, description: str, code: str) -> int:
        with _lock:
            row = self.conn.execute("SELECT id, version FROM tools WHERE name = ?", (name,)).fetchone()
            if row:
                self.conn.execute(
                    "UPDATE tools SET description = ?, code = ?, version = version + 1,"
                    " status = 'active', created_at = ? WHERE name = ?",
                    (description, code, _now(), name))
                tool_id = row["id"]
            else:
                cur = self.conn.execute(
                    "INSERT INTO tools (name, description, code, created_at) VALUES (?, ?, ?, ?)",
                    (name, description, code, _now()))
                tool_id = cur.lastrowid
            self.conn.commit()
            return tool_id

    def retire_tool(self, name: str) -> None:
        with _lock:
            self.conn.execute("UPDATE tools SET status = 'retired' WHERE name = ?", (name,))
            self.conn.commit()

    def list_tools(self) -> list:
        rows = self.conn.execute("SELECT * FROM tools ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    # ---------- evaluaciones y aprendizaje ----------
    def log_evaluation(self, task: str, agent: str, score: float, feedback: str) -> None:
        with _lock:
            self.conn.execute(
                "INSERT INTO evaluations (task, agent, score, feedback, created_at) VALUES (?, ?, ?, ?, ?)",
                (task, agent, score, feedback, _now()))
            self.conn.commit()

    def add_learning(self, rule: str, source: str = "auto") -> None:
        with _lock:
            exists = self.conn.execute(
                "SELECT id FROM learnings WHERE rule = ?", (rule,)).fetchone()
            if not exists:
                self.conn.execute(
                    "INSERT INTO learnings (rule, source, created_at) VALUES (?, ?, ?)",
                    (rule, source, _now()))
            self.conn.commit()

    def list_learnings(self, limit: int = 25) -> list:
        rows = self.conn.execute(
            "SELECT * FROM learnings ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        def count(table: str) -> int:
            return self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        avg = self.conn.execute("SELECT AVG(score) AS s FROM evaluations").fetchone()["s"]
        return {"memories": count("memories"), "messages": count("messages"),
                "tools": count("tools"), "evaluations": count("evaluations"),
                "learnings": count("learnings"),
                "avg_score": round(avg or 0.0, 3)}
from .r2_backup import restore_if_available

restore_if_available()

memory = Memory()
