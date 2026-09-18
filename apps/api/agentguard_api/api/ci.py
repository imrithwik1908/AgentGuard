from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard_api.db.session import get_session
from agentguard_api.schemas.evaluation import ReleaseDecision
from agentguard_api.services.evaluations import decide_release
from agentguard_api.services.security import AuthContext, get_auth_context

router = APIRouter(prefix="/ci", tags=["ci"])


class ReleaseGateResult(BaseModel):
    passed: bool
    exit_code: int
    decision: ReleaseDecision


@router.get("/release-gate", response_model=ReleaseGateResult)
async def read_release_gate(
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    minimum_pass_rate: Decimal = Query(default=Decimal("0.8000"), ge=0, le=1),
    maximum_regressions: int = Query(default=0, ge=0),
    allowed_score_drop: Decimal = Query(default=Decimal("0.0000"), ge=0, le=1),
    minimum_evaluation_coverage: Decimal = Query(default=Decimal("1.0000"), ge=0, le=1),
    required_evaluator: list[str] | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    decision = await decide_release(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        minimum_pass_rate=minimum_pass_rate.quantize(Decimal("0.0001")),
        maximum_regressions=maximum_regressions,
        allowed_score_drop=allowed_score_drop.quantize(Decimal("0.0001")),
        minimum_evaluation_coverage=minimum_evaluation_coverage.quantize(Decimal("0.0001")),
        required_evaluator_names=required_evaluator or [],
        workspace_id=auth.workspace_id,
    )
    passed = decision.decision == "PASS"
    return ReleaseGateResult(passed=passed, exit_code=0 if passed else 1, decision=decision)
