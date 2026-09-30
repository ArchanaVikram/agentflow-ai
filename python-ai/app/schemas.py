from typing import Literal, Optional

from pydantic import BaseModel, Field

ToolName = Literal["browser", "airtable", "gmail", "outlook", "sheets", "llm"]


class Task(BaseModel):
    id: str
    name: str
    description: str
    tool: ToolName
    depends_on: list[str] = []
    priority: int = 1
    requires_approval: bool = False
    status: Literal["pending", "running", "completed", "failed"] = "pending"


class PlanRequest(BaseModel):
    goal: str = Field(min_length=5, max_length=1000)
    workflow_id: Optional[str] = None
    user_id: Optional[str] = None


class PlanResponse(BaseModel):
    workflow_id: Optional[str] = None
    goal: str
    intent: str
    tasks: list[Task]


class RiskRequest(BaseModel):
    action: str = Field(min_length=2, max_length=500)
    tool: Optional[str] = None


class RiskResponse(BaseModel):
    score: int
    level: Literal["SAFE", "MEDIUM", "HIGH"]
    requires_approval: bool
    reason: str


class ExecuteRequest(BaseModel):
    workflow_id: Optional[str] = None
    task: Task
    context: dict = {}  # outputs of earlier tasks, keyed by task id
    approved: bool = False
    simulate_failure: Optional[Literal["unavailable", "flaky"]] = None  # for demos


class ExecuteResponse(BaseModel):
    workflow_id: Optional[str] = None
    task_id: str
    status: Literal["completed", "failed", "awaiting_approval"]
    output: dict = {}
    logs: list[str] = []
    error: Optional[str] = None


class WorkflowRunRequest(BaseModel):
    goal: str = Field(min_length=5, max_length=1000)
    workflow_id: Optional[str] = None
    # To resume a paused workflow, send back the tasks and results you received
    tasks: list[Task] = []
    results: dict = {}
    approved_tasks: list[str] = []
    validations: dict = {}
    # Demo helper, e.g. {"gmail": "unavailable"} or {"browser": "flaky"}
    simulate_failures: dict = {}


class WorkflowRunResponse(BaseModel):
    workflow_id: Optional[str] = None
    goal: str
    status: Literal["completed", "awaiting_approval", "failed", "escalated"]
    pending_task_id: Optional[str] = None
    tasks: list[Task]
    results: dict
    logs: list[str]
    validations: dict = {}
    confidence: Optional[int] = None
    recoveries: list[dict] = []


class ValidateRequest(BaseModel):
    workflow_id: Optional[str] = None
    task: Task
    output: dict = {}
    context: dict = {}


class ValidationCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class ValidateResponse(BaseModel):
    workflow_id: Optional[str] = None
    task_id: str
    passed: bool
    confidence: int
    checks: list[ValidationCheck]
    summary: str


class RecoverRequest(BaseModel):
    workflow_id: Optional[str] = None
    task: Task
    error: str
    attempt: int = 1


class RecoverResponse(BaseModel):
    task_id: str
    action: Literal["retry", "switch_tool", "escalate"]
    new_tool: Optional[ToolName] = None
    reason: str