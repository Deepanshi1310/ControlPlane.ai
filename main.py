from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.evaluation import router as evaluation_router


app = FastAPI(
    title="ControlPlane.ai",
    version="1.0.0",
    description="Real-time AI oversight and governance layer"
)

# Enable CORS for browser extension and client applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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