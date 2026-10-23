
"""Validaciones iniciales para Triad Studio."""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def validate_python_file(relative_path: str) -> dict:
    """Comprueba la sintaxis de un archivo Python del proyecto."""

    file_path = (PROJECT_ROOT / relative_path).resolve()

    # Impedir el acceso a archivos fuera del proyecto.
    if not file_path.is_relative_to(PROJECT_ROOT):
        return {
            "ok": False,
            "message": "La ruta esta fuera del proyecto."
        }

    if file_path.suffix.lower() != ".py":
        return {
            "ok": False,
            "message": "Solo se admiten archivos Python."
        }

    if not file_path.is_file():
        return {
            "ok": False,
            "message": "El archivo no existe."
        }

    try:
        source = file_path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(file_path))

        return {
            "ok": True,
            "message": "Sintaxis Python correcta.",
            "file": str(file_path.relative_to(PROJECT_ROOT))
        }

    except SyntaxError as error:
        return {
            "ok": False,
            "message": (
                f"Error de sintaxis en linea {error.lineno}: "
                f"{error.msg}"
            )
        }

    except (OSError, UnicodeError) as error:
        return {
            "ok": False,
            "message": f"No se pudo leer el archivo: {error}"
        }
