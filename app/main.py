from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Store Intelligence API")

# Mount dashboard static files
app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")

@app.get("/health")
def health_check():
    return {"status": "ok"}
