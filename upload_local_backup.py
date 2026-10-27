from pathlib import Path
import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv
root = Path(__file__).resolve().parent
load_dotenv(root / ".env", override=False)
load_dotenv(root / "backend" / ".env", override=False)
zip_value = os.getenv("TRIAD_BACKUP_ZIP")
zip_path = Path(zip_value) if zip_value else max(
    (Path.home() / "Desktop").glob("TRIAD_STUDIO_LOCAL_*.zip"),
    key=lambda p: p.stat().st_mtime
)
endpoint = os.getenv("R2_ENDPOINT", "")
bucket = os.getenv("R2_BUCKET", "triad-backups")
key_id = os.getenv("R2_KEY_ID", "")
secret = os.getenv("R2_SECRET", "")
prefix = os.getenv("R2_PREFIX", "triad").strip("/")
if not all([endpoint, bucket, key_id, secret]):
    raise SystemExit("Faltan credenciales R2.")
client = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=key_id,
    aws_secret_access_key=secret,
    region_name="auto",
    config=Config(signature_version="s3v4")
)
key = f"{prefix}/source-backups/{zip_path.name}"
client.upload_file(str(zip_path), bucket, key)
client.head_object(Bucket=bucket, Key=key)
print(f"SUBIDA VERIFICADA: {key}")
