from fastapi import APIRouter, Depends

from ...core.security import require_role, UserContext
from ...models.copilot import CopilotQueryRequest, CopilotQueryResponse
from ...services.copilot_service import CopilotService


router = APIRouter(tags=["copilot"])


service = CopilotService()


@router.post("/copilot/query", response_model=CopilotQueryResponse)
async def copilot_query(
    payload: CopilotQueryRequest,
    user: UserContext = Depends(require_role(["planner", "admin", "viewer"])),
) -> CopilotQueryResponse:
    return service.answer_query(payload)
