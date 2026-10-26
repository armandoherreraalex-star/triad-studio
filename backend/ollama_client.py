import json
import os
import urllib.request
import urllib.error


# ============================================================
# CONFIGURACIÓN
# ============================================================

# En local:
#   http://127.0.0.1:11434
#
# En Render:
#   Se configura mediante la variable OLLAMA_URL
#   o LLM_BASE_URL.
#
OLLAMA_URL = (
    os.getenv("OLLAMA_URL")
    or os.getenv("LLM_BASE_URL")
    or "http://127.0.0.1:11434"
).rstrip("/")

# Si alguien puso /v1 al final de LLM_BASE_URL,
# lo quitamos porque este cliente utiliza la API nativa de Ollama.
if OLLAMA_URL.endswith("/v1"):
    OLLAMA_URL = OLLAMA_URL[:-3].rstrip("/")


DEFAULT_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen2.5-coder:7b"
)

# API key opcional.
# No es necesaria para un Ollama local.
API_KEY = os.getenv("LLM_API_KEY", "").strip()


# ============================================================
# PETICIONES
# ============================================================

def request(endpoint, payload=None, timeout=180):
    url = f"{OLLAMA_URL}{endpoint}"

    data = None

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Si el proveedor cloud requiere API key,
    # se enviará como Bearer token.
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")

            if not raw:
                return {}

            return json.loads(raw)

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")

        raise RuntimeError(
            f"Error HTTP {exc.code} al conectar con el servicio de IA.\n"
            f"URL: {url}\n"
            f"Respuesta: {body[:1000]}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"No se pudo conectar con el servicio de IA.\n"
            f"URL: {url}\n"
            f"Motivo: {exc.reason}"
        ) from exc

    except TimeoutError as exc:
        raise RuntimeError(
            f"Tiempo de espera agotado al conectar con:\n{url}"
        ) from exc


# ============================================================
# OLLAMA
# ============================================================

def status():
    """
    Comprueba que el servidor Ollama/API esté disponible.
    """
    return request(
        "/api/version",
        timeout=10
    )


def list_models():
    """
    Obtiene los modelos disponibles.
    """
    result = request(
        "/api/tags",
        timeout=20
    )

    return result.get("models", [])


def chat(message, model=None, history=None):
    """
    Envía un mensaje al modelo.
    """

    model = model or DEFAULT_MODEL

    available_models = list_models()

    available = [
        m.get("name")
        for m in available_models
        if m.get("name")
    ]

    # Si el servidor informa modelos, verificamos que exista.
    if available and model not in available:

        # Algunos servicios pueden devolver
        # el modelo con una etiqueta diferente.
        matching = [
            name for name in available
            if name.split(":")[0] == model.split(":")[0]
        ]

        if matching:
            model = matching[0]
        else:
            raise RuntimeError(
                f"El modelo '{model}' no está disponible.\n"
                f"Modelos encontrados: {available}"
            )

    messages = list(history or [])

    messages.append({
        "role": "user",
        "content": message
    })

    result = request(
        "/api/chat",
        {
            "model": model,
            "messages": messages,
            "stream": False
        },
        timeout=300
    )

    message_result = result.get("message")

    if not message_result:
        raise RuntimeError(
            "El servicio de IA respondió, pero no devolvió "
            "el campo 'message'."
        )

    content = message_result.get("content")

    if content is None:
        raise RuntimeError(
            "El servicio de IA devolvió un mensaje sin contenido."
        )

    return content


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("TRIAD STUDIO - PRUEBA DE CONEXIÓN IA")
    print("=" * 60)

    print(f"\nServidor IA:")
    print(OLLAMA_URL)

    print(f"\nModelo:")
    print(DEFAULT_MODEL)

    print("\n1. Probando conexión...")

    try:

        version = status()

        print("CONEXIÓN CORRECTA")
        print("Versión:", version)

    except Exception as exc:

        print("\nERROR DE CONEXIÓN")
        print(type(exc).__name__)
        print(exc)

        raise SystemExit(1)

    print("\n2. Modelos disponibles...")

    try:

        models = list_models()

        if not models:

            print("No hay modelos registrados.")

        else:

            for model in models:
                print(
                    "-",
                    model.get("name", "modelo desconocido")
                )

    except Exception as exc:

        print("\nERROR OBTENIENDO MODELOS")
        print(type(exc).__name__)
        print(exc)

        raise SystemExit(1)

    print("\n3. Probando generación...")

    try:

        result = chat(
            "Responde solamente: CONEXION CORRECTA"
        )

        print("\nRespuesta del modelo:")
        print(result)

    except Exception as exc:

        print("\nERROR GENERANDO TEXTO")
        print(type(exc).__name__)
        print(exc)

        raise SystemExit(1)

    print("\n" + "=" * 60)
    print("PRUEBA TERMINADA")
    print("=" * 60)