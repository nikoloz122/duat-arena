from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.core.config import settings
from backend.core.startup import validate_production_config

validate_production_config()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=f"DUAT Arena — {settings.app_description}",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
# Wildcard origins and credentials cannot be combined per the CORS spec, so
# credentials stay disabled for the open MVP setup. Lock origins down before
# enabling credentials in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/", tags=["Health"])
async def root():
    """Root liveness endpoint. The canonical health check is GET /api/health."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "message": "DUAT Arena is ready for chaos testing.",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )