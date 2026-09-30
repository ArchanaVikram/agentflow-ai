from fastapi import APIRouter, Depends

from app.agents.executor import execute_task
from app.agents.planner import create_plan
from app.agents.recovery import decide_recovery
from app.agents.risk import analyze_risk
from app.agents.validator import validate_task
from app.memory import search_from_request, store_memory
from app.schemas import (
    ExecuteRequest,
    ExecuteResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryStoreRequest,
    MemoryStoreResponse,
    PlanRequest,
    PlanResponse,
    RecoverRequest,
    RecoverResponse,
    RiskRequest,
    RiskResponse,
    ValidateRequest,
    ValidateResponse,
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


@router.post("/agent/validate", response_model=ValidateResponse)
async def validate(req: ValidateRequest):
    return validate_task(req)


@router.post("/agent/recover", response_model=RecoverResponse)
async def recover(req: RecoverRequest):
    return decide_recovery(req)


@router.post("/agent/run", response_model=WorkflowRunResponse)
async def run(req: WorkflowRunRequest):
    return await run_workflow(req)


@router.post("/risk/analyze", response_model=RiskResponse)
async def risk(req: RiskRequest):
    return analyze_risk(req)


@router.post("/memory/store", response_model=MemoryStoreResponse)
async def memory_store(req: MemoryStoreRequest):
    return store_memory(req)


@router.post("/memory/search", response_model=MemorySearchResponse)
async def memory_search(req: MemorySearchRequest):
    return MemorySearchResponse(results=search_from_request(req))