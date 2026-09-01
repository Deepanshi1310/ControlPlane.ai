from fastapi import APIRouter
from app.models.evaluation import (
    EvaluationRequest,
    EvaluationResponse
)
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

    controlplane = ControlPlaneService()

    result = await controlplane.evaluate(
        request
    )

    return result