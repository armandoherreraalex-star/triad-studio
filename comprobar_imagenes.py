"""Comprueba y repara los retratos de los personajes.

Ejecutar:  python comprobar_imagenes.py
Busca las imágenes en todo el proyecto, las copia con el nombre correcto
a assets/characters/ y avisa de cualquier problema.
"""
import shutil
from pathlib import Path

BASE = Path(__file__).parent
CHARS = BASE / "assets" / "characters"
CANON = {"sylphiette": "sylphiette.png",
         "roxy": "roxy.png",
         "eris": "eris.png"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def find_images() -> list:
    """Busca imágenes parecidas a los personajes en todo el proyecto."""
    hits = []
    for p in BASE.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in IMG_EXT:
            continue
        if any(part in ("node_modules", ".venv", "__pycache__", "voice")
               for part in p.parts):
            continue
        stem = p.stem.lower()
        for key in CANON:
            if key in stem:
                hits.append((key, p))
                break
    return hits


def main() -> None:
    print(f"Buscando retratos en: {CHARS}\n")

    CHARS.mkdir(parents=True, exist_ok=True)
    hits = find_images()

    if not hits:
        print("NO SE HA ENCONTRADO NINGUNA IMAGEN de los personajes en el proyecto.")
        print("\nQué hacer:")
        print("  1. Genera o descarga las 3 imágenes (ver assets/characters/LEEME.txt)")
        print("  2. Cópialas en:  " + str(CHARS))
        print("  3. Nombres exactos: sylphiette.png  roxy.png  eris.png")
        return

    print("Imágenes encontradas:")
    for key, path in hits:
        print(f"  [{key}] {path}")

    print("\nCopiando al destino correcto...")
    for key, path in hits:
        dest = CHARS / CANON[key]
        try:
            shutil.copy2(path, dest)
            size_kb = dest.stat().st_size // 1024
            print(f"  OK  {CANON[key]}  ({size_kb} KB)")
        except Exception as exc:
            print(f"  ERROR con {path.name}: {exc}")

    print("\nComprobación final:")
    todo_ok = True
    for key, name in CANON.items():
        dest = CHARS / name
        if dest.is_file() and dest.stat().st_size > 1000:
            print(f"  LISTO  {name}")
        else:
            print(f"  FALTA  {name}  → sube la imagen con ese nombre exacto")
            todo_ok = False

    if todo_ok:
        print("\nTodo correcto. Ahora:")
        print("  1. Reinicia la app:  python main.py")
        print("  2. Abre el panel y recarga CON Ctrl+Mayús+R (borra la caché)")
        print("  Verás los tres retratos ilustrados en sus tarjetas.")
    else:
        print("\nFaltan imágenes. Súbelas y vuelve a ejecutar este script.")


if __name__ == "__main__":
    main()