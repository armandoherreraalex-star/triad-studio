from pathlib import Path
import re
import json
import os

ROOT = Path(__file__).resolve().parent

# Carpetas que normalmente NO necesitamos analizar a fondo
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    ".venv313",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

# Extensiones que nos interesa revisar
EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".html", ".css", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".env",
    ".md", ".txt", ".sh", ".bat", ".ps1"
}

# Patrones importantes para detectar dependencia de la PC
PATTERNS = {
    "LOCALHOST": r"(localhost|127\.0\.0\.1|0\.0\.0\.0)",
    "RUTA_WINDOWS": r"[A-Za-z]:\\Users\\|[A-Za-z]:\\\\Users\\\\",
    "RUTA_LOCAL_UNIX": r"/home/|/Users/|/mnt/",
    "SQLITE": r"(sqlite|\.db\b|sqlite3)",
    "ARCHIVOS_LOCALES": r"(open\(|Path\(|read_text\(|write_text\(|mkdir\(|os\.path)",
    "PUERTOS": r"(PORT\s*=|port\s*=|:\d{4,5})",
    "ENV": r"(os\.environ|os\.getenv|process\.env|dotenv|load_dotenv)",
    "RENDER": r"(render\.com|render\.yaml|render\.yml)",
    "CLOUDFLARE": r"(cloudflare|wrangler|workers)",
    "GITHUB": r"(github\.com|github)",
    "SUPABASE": r"(supabase)",
    "FIREBASE": r"(firebase)",
    "MONGODB": r"(mongodb|mongo)",
    "POSTGRES": r"(postgres|postgresql)",
    "MYSQL": r"(mysql)",
    "REDIS": r"(redis)",
    "SECRETOS": r"(API_KEY|SECRET_KEY|TOKEN|PASSWORD|PRIVATE_KEY|ACCESS_KEY)",
    "UPLOADS_LOCALES": r"(uploads|storage|media|temp|tmp)",
    "BASE_DIR": r"(BASE_DIR|ROOT_DIR|PROJECT_ROOT|__file__)",
}

results = []
files_scanned = 0
errors = []

def should_skip(path: Path):
    return any(part in EXCLUDE_DIRS for part in path.parts)

def scan_file(path: Path):
    global files_scanned

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        files_scanned += 1
    except Exception as e:
        errors.append(f"{path}: {e}")
        return

    lines = text.splitlines()

    for number, line in enumerate(lines, start=1):
        for category, pattern in PATTERNS.items():
            try:
                if re.search(pattern, line, re.IGNORECASE):
                    results.append({
                        "categoria": category,
                        "archivo": str(path.relative_to(ROOT)),
                        "linea": number,
                        "contenido": line.strip()[:500]
                    })
            except re.error:
                pass


print("=" * 80)
print(" TRIAD STUDIO - ESCANER DE DEPENDENCIAS LOCALES / NUBE")
print("=" * 80)
print()
print(f"Proyecto: {ROOT}")
print()

# ---------------------------------------------------------
# 1. ESCANEAR ARCHIVOS
# ---------------------------------------------------------

for path in ROOT.rglob("*"):
    if not path.is_file():
        continue

    if should_skip(path):
        continue

    if path.suffix.lower() in EXTENSIONS or path.name.startswith(".env"):
        scan_file(path)

# ---------------------------------------------------------
# 2. ESTRUCTURA DEL PROYECTO
# ---------------------------------------------------------

print("\n" + "=" * 80)
print("1. ESTRUCTURA PRINCIPAL")
print("=" * 80)

for item in sorted(ROOT.iterdir(), key=lambda x: x.name.lower()):
    if item.name in EXCLUDE_DIRS:
        continue

    tipo = "CARPETA" if item.is_dir() else "ARCHIVO"
    print(f"[{tipo}] {item.name}")

# ---------------------------------------------------------
# 3. ARCHIVOS DE DESPLIEGUE
# ---------------------------------------------------------

print("\n" + "=" * 80)
print("2. ARCHIVOS RELACIONADOS CON DESPLIEGUE")
print("=" * 80)

deployment_files = [
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "render.yaml",
    "render.yml",
    "vercel.json",
    "netlify.toml",
    "wrangler.toml",
    "wrangler.json",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Procfile",
    ".env",
    ".env.example",
]

found_deployment = []

for name in deployment_files:
    path = ROOT / name
    if path.exists():
        found_deployment.append(name)
        print(f"[ENCONTRADO] {name}")

if not found_deployment:
    print("[NINGUNO] No se encontraron archivos comunes de despliegue.")

# ---------------------------------------------------------
# 4. RESULTADOS POR CATEGORIA
# ---------------------------------------------------------

categories = {}

for result in results:
    categories.setdefault(result["categoria"], []).append(result)

print("\n" + "=" * 80)
print("3. HALLAZGOS")
print("=" * 80)

if not results:
    print("No se encontraron patrones importantes.")
else:
    for category, items in sorted(categories.items()):
        print(f"\n--- {category} ({len(items)}) ---")

        # Mostrar máximo 30 por categoría para no hacer una salida gigantesca
        for item in items[:30]:
            print(
                f"{item['archivo']}:{item['linea']} -> "
                f"{item['contenido']}"
            )

        if len(items) > 30:
            print(f"... y {len(items) - 30} coincidencias más.")

# ---------------------------------------------------------
# 5. ARCHIVOS GRANDES
# ---------------------------------------------------------

print("\n" + "=" * 80)
print("4. ARCHIVOS GRANDES")
print("=" * 80)

large_files = []

for path in ROOT.rglob("*"):
    if not path.is_file():
        continue

    if should_skip(path):
        continue

    try:
        size_mb = path.stat().st_size / (1024 * 1024)

        if size_mb >= 5:
            large_files.append((size_mb, path.relative_to(ROOT)))

    except Exception:
        pass

if large_files:
    for size, path in sorted(large_files, reverse=True):
        print(f"{size:.2f} MB -> {path}")
else:
    print("No hay archivos de más de 5 MB.")

# ---------------------------------------------------------
# 6. VARIABLES DE ENTORNO
# ---------------------------------------------------------

print("\n" + "=" * 80)
print("5. VARIABLES DE ENTORNO DETECTADAS")
print("=" * 80)

env_files = list(ROOT.glob(".env*"))

if env_files:
    for env in env_files:
        print(f"[ENCONTRADO] {env.name}")
else:
    print("No se encontraron archivos .env.")

# ---------------------------------------------------------
# 7. INFORMACION DE GIT
# ---------------------------------------------------------

print("\n" + "=" * 80)
print("6. GIT / GITHUB")
print("=" * 80)

git_dir = ROOT / ".git"

if git_dir.exists():
    print("[OK] El proyecto tiene repositorio Git local.")

    config = git_dir / "config"

    if config.exists():
        try:
            text = config.read_text(encoding="utf-8", errors="ignore")

            remotes = re.findall(
                r"url\s*=\s*(.+)",
                text,
                re.IGNORECASE
            )

            if remotes:
                for remote in remotes:
                    print(f"Remote: {remote.strip()}")
            else:
                print("[ADVERTENCIA] No se encontró remote de GitHub.")
        except Exception as e:
            print(f"No se pudo leer .git/config: {e}")
else:
    print("[ADVERTENCIA] No se encontró carpeta .git.")

# ---------------------------------------------------------
# 8. RESUMEN AUTOMATICO
# ---------------------------------------------------------

print("\n" + "=" * 80)
print("7. RESUMEN PARA MIGRACION A LA NUBE")
print("=" * 80)

warnings = []

if "LOCALHOST" in categories:
    warnings.append(
        "Hay referencias a localhost/127.0.0.1. "
        "Debemos determinar si son internas o URLs que deben cambiarse."
    )

if "RUTA_WINDOWS" in categories:
    warnings.append(
        "Hay rutas de Windows dentro del código. "
        "Esto puede impedir que funcione igual en Render/Linux."
    )

if "SQLITE" in categories:
    warnings.append(
        "Se detectó SQLite/archivos .db. "
        "Render puede perder almacenamiento local al reiniciar/recrear el servicio."
    )

if "ARCHIVOS_LOCALES" in categories:
    warnings.append(
        "Hay operaciones de lectura/escritura de archivos. "
        "Debemos comprobar si esos datos necesitan almacenamiento persistente."
    )

if "UPLOADS_LOCALES" in categories:
    warnings.append(
        "Se detectaron carpetas relacionadas con uploads/storage/media."
    )

if "ENV" not in categories:
    warnings.append(
        "No se detectó claramente un sistema de variables de entorno."
    )

if "RENDER" not in categories:
    warnings.append(
        "No se detectó configuración clara de Render."
    )

if "CLOUDFLARE" not in categories:
    warnings.append(
        "No se detectó configuración clara de Cloudflare."
    )

if warnings:
    for i, warning in enumerate(warnings, start=1):
        print(f"{i}. {warning}")
else:
    print("No se detectaron problemas evidentes relacionados con la migración.")

# ---------------------------------------------------------
# 9. GUARDAR REPORTE JSON
# ---------------------------------------------------------

report = {
    "proyecto": str(ROOT),
    "archivos_escaneados": files_scanned,
    "hallazgos": results,
    "archivos_despliegue": found_deployment,
    "archivos_grandes": [
        {
            "archivo": str(path),
            "tamano_mb": round(size, 2)
        }
        for size, path in large_files
    ],
    "advertencias": warnings,
    "errores": errors,
}

output = ROOT / "REPORTE_NUBE.json"

try:
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\n" + "=" * 80)
    print("REPORTE GUARDADO")
    print("=" * 80)
    print(output)

except Exception as e:
    print(f"No se pudo guardar el reporte: {e}")

print("\n" + "=" * 80)
print("ESCANEO TERMINADO")
print("=" * 80)
print()