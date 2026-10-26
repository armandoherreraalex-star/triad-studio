"""Crea la carpeta data/ y la base de datos del agente con todas sus tablas.

Ejecutar UNA vez:   python crear_base.py
Se puede ejecutar todas las veces que se quiera: no borra nada,
solo crea lo que falta.
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
DB_PATH = DATA_DIR / "triad_memory.db"

SCHEMA = """
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


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA)
    conn.commit()

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    conn.close()

    print("=" * 58)
    print("  Base de datos del agente creada correctamente")
    print(f"  Ubicación: {DB_PATH}")
    print(f"  Tablas: {', '.join(t[0] for t in tables)}")
    print("=" * 58)
    print("Ahora ejecuta:  python main.py")


if __name__ == "__main__":
    main()