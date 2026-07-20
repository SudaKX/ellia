from fastapi import FastAPI

app = FastAPI(title="Ellia Mythos API", version="0.1.0")


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
