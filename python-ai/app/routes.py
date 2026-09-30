from fastapi import APIRouter, Depends

from app.agents.executor import execute_task
from app.agents.planner import create_plan
from app.agents.risk import analyze_risk
from app.schemas import (
    ExecuteRequest,
    ExecuteResponse,
    PlanRequest,
    PlanResponse,
    RiskRequest,
    RiskResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from app.security import verify_api_key
from app.workflow import run_workflow

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/agent/plan", response_model=PlanResponse)
async def plan(req: PlanRequest):
    return await create_plan(req)


@router.post("/agent/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    return await execute_task(req)


@router.post("/agent/run", response_model=WorkflowRunResponse)
async def run(req: WorkflowRunRequest):
    return await run_workflow(req)


@router.post("/risk/analyze", response_model=RiskResponse)
async def risk(req: RiskRequest):
    return analyze_risk(req)