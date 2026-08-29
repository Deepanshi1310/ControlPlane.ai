from fastapi import APIRouter, Depends

from app.models.evaluation import (
    EvaluationRequest,
    EvaluationResponse
)

from app.services.gemini_service import GeminiService
from app.services.controlplane_service import ControlPlaneService


router = APIRouter(
    prefix="/api/v1/evaluation",
    tags=["Evaluation"]
)


@router.post(
    "/evaluate",
    response_model=EvaluationResponse
)
async def evaluate(request: EvaluationRequest):

    gemini_service = GeminiService()

    controlplane = ControlPlaneService(
        gemini_service
    )

    result = await controlplane.evaluate(
        request
    )

    return result