
import io
import os
import sqlite3
import tempfile
import zipfile
import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from .config import BASE_DIR, DATA_DIR, WORKSPACE_DIR, CUSTOM_TOOLS_DIR

log = logging.getLogger(__name__)

BUCKET = os.getenv("R2_BUCKET", "triad-backups")
PREFIX = os.getenv("R2_PREFIX", "triad").strip("/")
DB_PATH = DATA_DIR / "triad_memory.db"


def _client():
    endpoint = os.getenv("R2_ENDPOINT")
    key_id = os.getenv("R2_KEY_ID")
    secret = os.getenv("R2_SECRET")

    if not all((endpoint, key_id, secret, BUCKET)):
        raise RuntimeError("Faltan variables de configuración de R2")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name="auto",
    )


def _object_key():
    return f"{PREFIX}/backup.zip" if PREFIX else "backup.zip"


def restore_if_available():
    """Restaura la copia antes de inicializar la base de datos."""
    try:
        client = _client()
        response = client.get_object(
            Bucket=BUCKET, Key=_object_key()
        )
        content = response["Body"].read()
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404", "NotFound"):
            log.info("Todavía no existe una copia en R2.")
            return False
        log.exception("No se pudo descargar la copia de R2.")
        return False
    except Exception:
        log.exception("R2 no está disponible para restaurar.")
        return False

    # No sobrescribir una base de datos local que ya contiene datos.
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        log.info("Ya existe una base local; no se restaura encima.")
        return False

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for item in archive.infolist():
                destination = (BASE_DIR / item.filename).resolve()
                if not destination.is_relative_to(BASE_DIR.resolve()):
                    raise ValueError("Ruta no permitida en la copia")
            archive.extractall(BASE_DIR)

        log.info("Copia de R2 restaurada.")
        return True
    except Exception:
        log.exception("La copia descargada no se pudo restaurar.")
        return False


def backup_all(db_connection):
    """Sube una instantánea de memoria y las carpetas de trabajo."""
    client = _client()

    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        snapshot = temp_path / "triad_memory.db"

        with sqlite3.connect(str(snapshot)) as destination:
            db_connection.backup(destination)

        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer, "w", zipfile.ZIP_DEFLATED
        ) as archive:
            if snapshot.exists():
                archive.write(snapshot, "data/triad_memory.db")

            for folder in (DATA_DIR, WORKSPACE_DIR, CUSTOM_TOOLS_DIR):
                if not folder.exists():
                    continue
                for file in folder.rglob("*"):
                    if not file.is_file():
                        continue
                    if file.name in (
                        "triad_memory.db",
                        "triad_memory.db-wal",
                        "triad_memory.db-shm",
                    ):
                        continue
                    archive.write(file, file.relative_to(BASE_DIR))

        buffer.seek(0)
        client.put_object(
            Bucket=BUCKET,
            Key=_object_key(),
            Body=buffer.getvalue(),
            ContentType="application/zip",
        )
        log.info("Copia subida correctamente a R2.")
