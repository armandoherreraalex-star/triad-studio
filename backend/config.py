import os
from pathlib import Path
from dataclasses import dataclass

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = BASE_DIR / "workspace"
REPORTS_DIR = WORKSPACE_DIR / "reports"
CUSTOM_TOOLS_DIR = BASE_DIR / "custom_tools"
FRONTEND_DIR = BASE_DIR / "frontend"

for _d in (DATA_DIR, WORKSPACE_DIR, REPORTS_DIR, CUSTOM_TOOLS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5-coder:7b")
    llm_timeout: int = int(os.getenv("LLM_TIMEOUT", "180"))
    max_steps: int = int(os.getenv("MAX_STEPS", "6"))
    command_timeout: int = int(os.getenv("COMMAND_TIMEOUT", "60"))
       host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))


settings = Settings()

