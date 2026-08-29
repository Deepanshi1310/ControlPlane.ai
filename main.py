from fastapi import FastAPI

from app.routers.evaluation import router as evaluation_router


app = FastAPI(
    title="ControlPlane.ai",
    version="1.0.0",
    description="Real-time AI oversight and governance layer"
)


app.include_router(
    evaluation_router
)


@app.get("/")
async def root():

    return {
        "name": "ControlPlane.ai",
        "status": "operational"
    }


@app.get("/health")
async def health():

    return {
        "status": "healthy"
    }