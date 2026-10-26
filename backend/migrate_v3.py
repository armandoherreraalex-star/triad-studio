"""Migra los nombres antiguos a la forma corta. Ejecutar UNA vez:
python -m backend.migrate_v3
"""
import sqlite3

from .config import DATA_DIR

DB = DATA_DIR / "triad_memory.db"
RENAME = {"Roxy": "Roxy", "Eris": "Eris"}


def migrate() -> None:
    if not DB.exists():
        print("No hay base de datos todavía: nada que migrar. Todo correcto.")
        return
    conn = sqlite3.connect(str(DB))
    total = 0
    for old, new in RENAME.items():
        for table, col in (("messages", "agent"), ("evaluations", "agent")):
            cur = conn.execute(f"UPDATE {table} SET {col} = ? WHERE {col} = ?",
                               (new, old))
            total += cur.rowcount
        cur = conn.execute(
            "UPDATE memories SET tags = REPLACE(tags, ?, ?) WHERE tags LIKE ?",
            (new, old, f"%{old}%"))
        total += cur.rowcount
        cur = conn.execute(
            "UPDATE learnings SET rule = REPLACE(rule, ?, ?) WHERE rule LIKE ?",
            (new, old, f"%{old}%"))
        total += cur.rowcount
    conn.commit()
    conn.close()
    print(f"Migración completada: {total} registros actualizados a nombres cortos.")


if __name__ == "__main__":
    migrate()