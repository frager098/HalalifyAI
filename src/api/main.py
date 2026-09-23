from fastapi import FastAPI

app = FastAPI(
    title="Halalify AI Service",
    description=(
        "AI service for Shariah screening, stock classification, "
        "portfolio optimization and backtesting."
    ),
    version="0.1.0",
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Halalify AI Service",
        "documentation": "/docs",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy", 
        "service": "halalify-ai",
        "version": "0.1.0",
    }