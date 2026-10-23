"""Punto de entrada de TRIAD STUDIO."""
import uvicorn
from backend.config import settings

if __name__ == "__main__":
    print("=" * 62)
    print("  TRIAD STUDIO  |  Sylphiette  ·  Roxy Migurdia  ·  Eris Boreas Greyrat")
    print(f"  Panel: http://{settings.host}:{settings.port}")
    print("=" * 62)
    uvicorn.run("backend.server:app", host=settings.host, port=settings.port, log_level="info")