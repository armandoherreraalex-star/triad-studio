"""Persistencia en la nube: respalda y restaura la memoria del agente automáticamente.

Almacén: Cloudflare R2 (plan gratuito, 10 GB). Nada se pierde aunque el
servidor apague o redespliegue el disco.

Si no hay credenciales de R2 configuradas (variables de entorno R2_*),
el sistema funciona igualmente en modo local: la memoria se guarda en
data/triad_memory.db como siempre.
"""
import io
import os
import tarfile
import threading
import time

from .config import BASE_DIR

BUCKET = os.getenv("R2_BUCKET", "triad-backups")
PREFIX = os.getenv("R2_PREFIX", "triad").strip("/")
FOLDERS = ("data", "workspace", "custom_tools")
RETRIES = 3


def _enabled() -> bool:
    """La persistencia en la nube solo actúa si las credenciales están completas."""
    return bool(os.getenv("R2_ENDPOINT") and os.getenv("R2_KEY_ID")
                and os.getenv("R2_SECRET") and BUCKET)


def _client():
    """Cliente S3 compatible con Cloudflare R2. Falla con mensaje claro si falta boto3."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError(
            "Falta la librería boto3. Añade 'boto3==1.35.24' a requirements.txt "
            "y ejecuta: pip install -r requirements.txt") from exc
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"].strip(),
        aws_access_key_id=os.environ["R2_KEY_ID"].strip(),
        aws_secret_access_key=os.environ["R2_SECRET"].strip(),
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": RETRIES}))


def test_connection() -> str:
    """Prueba la conexión paso a paso y devuelve un diagnóstico exacto."""
    if not _enabled():
        return ("modo local (sin nube): faltan variables R2_ENDPOINT / R2_KEY_ID / "
                "R2_SECRET en .env — la memoria se guarda igualmente en data/")
    try:
        s3 = _client()
    except Exception as exc:
        return f"ERROR al crear el cliente: {exc}"
    try:
        s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/", MaxKeys=1)
    except Exception as exc:
        return (f"ERROR al conectar con R2 (bucket '{BUCKET}'): {exc}\n"
                "→ Revisa: endpoint https://TU_ID.r2.cloudflarestorage.com, "
                "token con permiso Object Read & Write, y nombre exacto del bucket.")
    try:
        result = backup_now()
        return f"CONEXIÓN CORRECTA. {result}"
    except Exception as exc:
        return f"Conecta pero FALLA al subir: {exc}"


def backup_now() -> str:
    """Comprime data/, workspace/ y custom_tools/ y los sube a R2."""
    if not _enabled():
        return "respaldo en la nube desactivado (modo local: todo queda en data/)"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name in FOLDERS:
            src = BASE_DIR / name
            if src.exists():
                tar.add(src, arcname=name)
    buf.seek(0)
    key = f"{PREFIX}/triad-{int(time.time())}.tar.gz"
    _client().upload_fileobj(buf, BUCKET, key)
    return f"respaldo subido: {key}"


def restore_latest() -> str:
    """Descubre el respaldo más reciente y lo restaura. Se ejecuta al arrancar."""
    if not _enabled():
        return "local (data/triad_memory.db)"
    try:
        s3 = _client()
        resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/")
        items = [o for o in resp.get("Contents", []) if o["Key"].endswith(".tar.gz")]
        if not items:
            return "no hay respaldos previos: memoria nueva"
        latest = max(items, key=lambda o: o["LastModified"])
        buf = io.BytesIO()
        s3.download_fileobj(BUCKET, latest["Key"], buf)
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            tar.extractall(BASE_DIR)
        return f"memoria restaurada desde {latest['Key']}"
    except Exception as exc:
        return f"no se pudo restaurar (la app sigue funcionando): {exc}"


def start_autobackup(interval_seconds: int = 1800) -> None:
    """Copia de seguridad automática cada 30 minutos en un hilo aparte."""
    def loop():
        while True:
            time.sleep(interval_seconds)
            try:
                print("[persist]", backup_now())
            except Exception as exc:
                print("[persist] error de respaldo:", exc)
    if _enabled():
        threading.Thread(target=loop, daemon=True).start()