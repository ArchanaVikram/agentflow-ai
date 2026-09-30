from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.executor import execute_task
from app.agents.planner import create_plan
from app.agents.recovery import decide_recovery
from app.agents.validator import validate_task
from app.schemas import (
    ExecuteRequest,
    PlanRequest,
    RecoverRequest,
    Task,
    ValidateRequest,
    WorkflowRunRequest,
    WorkflowRunResponse,
)


class WorkflowState(TypedDict):
    goal: str
    workflow_id: Optional[str]
    tasks: list[Task]
    results: dict
    validations: dict
    approved_tasks: list[str]
    simulate_failures: dict
    attempts: dict
    recoveries: list
    logs: list[str]
    status: str
    pending_task_id: Optional[str]


async def plan_node(state: WorkflowState) -> dict:
    """Step 1: create the plan (or reuse it when resuming)."""
    if state["tasks"]:
        return {
            "status": "running",
            "logs": state["logs"] + ["Resuming workflow with the existing plan"],
        }
    plan = await create_plan(PlanRequest(goal=state["goal"], workflow_id=state["workflow_id"]))
    return {
        "tasks": plan.tasks,
        "status": "running",
        "logs": state["logs"] + [f"Planner created {len(plan.tasks)} tasks"],
    }


def _next_task(tasks: list[Task]) -> Optional[Task]:
    """Pick the next pending task whose dependencies are all completed."""
    done = {t.id for t in tasks if t.status == "completed"}
    ready = [t for t in tasks if t.status == "pending" and all(d in done for d in t.depends_on)]
    ready.sort(key=lambda t: t.priority)
    return ready[0] if ready else None


def _handle_failure(state: WorkflowState, tasks: list[Task], task: Task, error: str, logs: list[str], validations: dict) -> dict:
    """Ask the Recovery agent what to do, then follow its decision."""
    attempts = dict(state["attempts"])
    attempts[task.id] = attempts.get(task.id, 0) + 1

    decision = decide_recovery(
        RecoverRequest(workflow_id=state["workflow_id"], task=task, error=error, attempt=attempts[task.id])
    )
    logs = logs + [f"Recovery: {decision.action} - {decision.reason}"]
    recoveries = state["recoveries"] + [
        {
            "task_id": task.id,
            "error": error,
            "action": decision.action,
            "new_tool": decision.new_tool,
            "reason": decision.reason,
        }
    ]
    update = {
        "tasks": tasks,
        "attempts": attempts,
        "recoveries": recoveries,
        "validations": validations,
        "logs": logs,
    }

    if decision.action == "retry":
        task.status = "pending"
        return {**update, "status": "running"}

    if decision.action == "switch_tool":
        task.tool = decision.new_tool
        task.status = "pending"
        return {**update, "status": "running"}

    task.status = "failed"
    return {**update, "status": "escalated", "pending_task_id": task.id}


async def run_next_node(state: WorkflowState) -> dict:
    """Step 2: run one task, validate it, and recover if something goes wrong."""
    tasks = list(state["tasks"])
    task = _next_task(tasks)

    if task is None:
        if all(t.status == "completed" for t in tasks):
            return {"status": "completed", "pending_task_id": None, "logs": state["logs"] + ["Workflow completed"]}
        return {"status": "failed", "logs": state["logs"] + ["Workflow stopped: no task can run"]}

    # Demo helper: decide whether to simulate a failure for this task
    mode = state["simulate_failures"].get(task.tool)
    attempt_no = state["attempts"].get(task.id, 0)
    simulate = mode if (mode == "unavailable" or (mode == "flaky" and attempt_no == 0)) else None

    result = await execute_task(
        ExecuteRequest(
            workflow_id=state["workflow_id"],
            task=task,
            context=state["results"],
            approved=task.id in state["approved_tasks"],
            simulate_failure=simulate,
        )
    )
    logs = state["logs"] + result.logs

    if result.status == "awaiting_approval":
        return {"status": "awaiting_approval", "pending_task_id": task.id, "logs": logs}

    if result.status == "failed":
        return _handle_failure(state, tasks, task, result.error or "Unknown error", logs, state["validations"])

    # The task ran: now the Validator checks the result
    validation = validate_task(
        ValidateRequest(
            workflow_id=state["workflow_id"],
            task=task,
            output=result.output,
            context=state["results"],
        )
    )
    logs = logs + [f"Validator: {validation.summary} (confidence {validation.confidence}%)"]
    validations = dict(state["validations"])
    validations[task.id] = validation.model_dump()

    if not validation.passed:
        return _handle_failure(
            state, tasks, task, f"Validation failed: {validation.summary}", logs + [f"Validation failed for task {task.id}"], validations
        )

    task.status = "completed"
    results = dict(state["results"])
    results[task.id] = result.output
    return {
        "tasks": tasks,
        "results": results,
        "validations": validations,
        "pending_task_id": None,
        "logs": logs,
        "status": "running",
    }


def _route(state: WorkflowState) -> str:
    return "run_next" if state["status"] == "running" else END


graph = StateGraph(WorkflowState)
graph.add_node("plan", plan_node)
graph.add_node("run_next", run_next_node)
graph.set_entry_point("plan")
graph.add_edge("plan", "run_next")
graph.add_conditional_edges("run_next", _route, {"run_next": "run_next", END: END})
workflow_app = graph.compile()


async def run_workflow(req: WorkflowRunRequest) -> WorkflowRunResponse:
    initial: WorkflowState = {
        "goal": req.goal,
        "workflow_id": req.workflow_id,
        "tasks": req.tasks,
        "results": req.results,
        "validations": req.validations,
        "approved_tasks": req.approved_tasks,
        "simulate_failures": req.simulate_failures,
        "attempts": {},
        "recoveries": [],
        "logs": [],
        "status": "running",
        "pending_task_id": None,
    }
    final = await workflow_app.ainvoke(initial, config={"recursion_limit": 50})

    scores = [v["confidence"] for v in final["validations"].values()]
    confidence = round(sum(scores) / len(scores)) if scores else None

    return WorkflowRunResponse(
        workflow_id=final["workflow_id"],
        goal=final["goal"],
        status=final["status"],
        pending_task_id=final["pending_task_id"],
        tasks=final["tasks"],
        results=final["results"],
        logs=final["logs"],
        validations=final["validations"],
        confidence=confidence,
        recoveries=final["recoveries"],
    )