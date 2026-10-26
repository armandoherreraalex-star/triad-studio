from fastapi import FastAPI
app = FastAPI(title="TRIAD STUDIO")
@app.get("/")
def inicio():
    return {"status": "ok", "message": "TRIAD STUDIO funcionando"}
@app.get("/health")
def health():
    return {"status": "healthy"}
