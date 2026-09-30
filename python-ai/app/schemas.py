from typing import Literal, Optional

from pydantic import BaseModel, Field

ToolName = Literal["browser", "airtable", "gmail", "outlook", "sheets", "llm"]
MemoryType = Literal["workflow_success", "workflow_failure", "preference", "note"]


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
    user_id: Optional[str] = None
    # To resume a paused workflow, send back the tasks and results you received
    tasks: list[Task] = []
    results: dict = {}
    approved_tasks: list[str] = []
    validations: dict = {}
    risks: dict = {}
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
    risks: dict = {}
    memories_used: list[dict] = []


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


class MemoryStoreRequest(BaseModel):
    user_id: Optional[str] = None
    type: MemoryType = "note"
    text: str = Field(min_length=3, max_length=2000)
    metadata: dict = {}


class MemoryStoreResponse(BaseModel):
    id: str
    total_memories: int


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    user_id: Optional[str] = None
    type: Optional[MemoryType] = None
    top_k: int = Field(default=3, ge=1, le=10)


class MemorySearchResult(BaseModel):
    id: str
    type: str
    text: str
    score: float
    metadata: dict = {}
    created_at: str


class MemorySearchResponse(BaseModel):
    results: list[MemorySearchResult]