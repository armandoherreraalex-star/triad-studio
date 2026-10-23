import json
import urllib.request
import urllib.error
OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"
def request(endpoint, payload=None, timeout=180):
    url = f"{OLLAMA_URL}{endpoint}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers=headers
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))
def status():
    return request("/api/version", timeout=5)
def list_models():
    return request("/api/tags", timeout=10).get("models", [])
def chat(message, model=DEFAULT_MODEL, history=None):
    available = [m["name"] for m in list_models()]
    if model not in available:
        raise RuntimeError(
            f"El modelo '{model}' no está disponible. "
            f"Modelos encontrados: {available}"
        )
    messages = list(history or [])
    messages.append({"role": "user", "content": message})
    result = request(
        "/api/chat",
        {
            "model": model,
            "messages": messages,
            "stream": False
        },
        timeout=300
    )
    return result["message"]["content"]
if __name__ == "__main__":
    try:
        print("1. Conexión con Ollama...")
        print(status())
        print("\n2. Modelos disponibles:")
        models = list_models()
        for model in models:
            print("-", model["name"])
        if not models:
            print("\nNo hay modelos registrados en Ollama.")
            print("La conexión funciona, pero no se puede generar texto todavía.")
        else:
            print("\n3. Probando generación...")
            print(chat("Responde solamente: CONEXION CORRECTA"))
    except Exception as exc:
        print(f"\nERROR: {type(exc).__name__}: {exc}")
