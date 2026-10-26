"""Voz neuronal por personaje. Cada una con su timbre, ritmo y tono.

Sylphiette → joven y dulce    (voz femenina, tono alto, ritmo normal)
Roxy       → serena y pausada (voz femenina madura, tono profundo, ritmo lento)
Eris       → brillante y rápida (voz femenina enérgica, ritmo vivo)

Requiere: pip install edge-tts
"""
import hashlib
import re

from .config import BASE_DIR

VOICE_DIR = BASE_DIR / "assets" / "voice"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

CHARACTERS = {
    "Sylphiette": {"voice": "es-MX-DaliaNeural", "rate": "+2%", "pitch": "+8Hz"},
    "Roxy":       {"voice": "es-CL-CatalinaNeural", "rate": "-8%", "pitch": "-6Hz"},
    "Eris":       {"voice": "es-ES-ElviraNeural", "rate": "+12%", "pitch": "+3Hz"},
}

DEFAULT = {"voice": "es-MX-DaliaNeural", "rate": "+0%", "pitch": "+0Hz"}


def available() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def _clean(text: str) -> str:
    return re.sub(r"[#*`>\[\]|{}]", "", str(text)).strip()[:380]


def synth(agent: str, text: str) -> bytes:
    """Genera el MP3 del personaje. Caché para no repetir trabajo."""
    import asyncio

    import edge_tts

    clean = _clean(text)
    if not clean:
        raise ValueError("Texto vacío para la voz.")
    cfg = CHARACTERS.get(agent, DEFAULT)

    key = hashlib.sha1(f"{agent}|{cfg}|{clean}".encode("utf-8")).hexdigest()[:24]
    cache_file = VOICE_DIR / f"{key}.mp3"
    if cache_file.exists():
        return cache_file.read_bytes()

    async def _run() -> bytes:
        com = edge_tts.Communicate(clean, cfg["voice"],
                                   rate=cfg["rate"], pitch=cfg["pitch"])
        buf = bytearray()
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)

    data = asyncio.run(_run())
    if not data:
        raise RuntimeError("El motor neuronal no devolvió audio.")
    cache_file.write_bytes(data)
    old = sorted(VOICE_DIR.glob("*.mp3"), key=lambda p: p.stat().st_mtime)
    for stale in old[:-300]:
        stale.unlink(missing_ok=True)
    return data


def greeting(agent: str) -> str:
    return {
        "Sylphiette": "Hola, soy Sylphiette. Interfaz, diseño y documentación listas.",
        "Roxy": "Roxy, aquí. Arquitectura, datos e inteligencia artificial en línea.",
        "Eris": "¡Eris lista! Sistemas, automatización y pruebas. Dime qué ejecutamos.",
    }.get(agent, f"{agent}, en línea.")