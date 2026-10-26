"""Punto de entrada de TRIAD STUDIO — con memoria persistente y voz neuronal."""
import uvicorn

from backend.config import settings
from backend.persist import restore_latest, start_autobackup, test_connection

if __name__ == "__main__":
    print("=" * 62)
    print("  TRIAD STUDIO  |  Sylphiette  ·  Roxy  ·  Eris")
    print(f"  Panel: http://{settings.host}:{settings.port}")
    print(f"  Memoria: {restore_latest()}")
    print(f"  Nube: {test_connection()}")
    print("=" * 62)
    start_autobackup()
    uvicorn.run("backend.server:app", host=settings.host, port=settings.port,
                log_level="info")