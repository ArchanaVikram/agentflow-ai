from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.executor import execute_task
from app.agents.planner import create_plan
from app.schemas import (
    ExecuteRequest,
    PlanRequest,
    Task,
    WorkflowRunRequest,
    WorkflowRunResponse,
)


class WorkflowState(TypedDict):
    goal: str
    workflow_id: Optional[str]
    tasks: list[Task]
    results: dict
    approved_tasks: list[str]
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


async def run_next_node(state: WorkflowState) -> dict:
    """Step 2: run one task. This node repeats until the workflow stops."""
    tasks = list(state["tasks"])
    task = _next_task(tasks)

    if task is None:
        if all(t.status == "completed" for t in tasks):
            return {"status": "completed", "pending_task_id": None, "logs": state["logs"] + ["Workflow completed"]}
        return {"status": "failed", "logs": state["logs"] + ["Workflow stopped: no task can run"]}

    result = await execute_task(
        ExecuteRequest(
            workflow_id=state["workflow_id"],
            task=task,
            context=state["results"],
            approved=task.id in state["approved_tasks"],
        )
    )
    logs = state["logs"] + result.logs

    if result.status == "awaiting_approval":
        return {"status": "awaiting_approval", "pending_task_id": task.id, "logs": logs}

    task.status = result.status
    if result.status == "completed":
        results = dict(state["results"])
        results[task.id] = result.output
        return {"tasks": tasks, "results": results, "pending_task_id": None, "logs": logs, "status": "running"}

    return {"tasks": tasks, "logs": logs, "status": "failed"}


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
        "approved_tasks": req.approved_tasks,
        "logs": [],
        "status": "running",
        "pending_task_id": None,
    }
    final = await workflow_app.ainvoke(initial, config={"recursion_limit": 50})
    return WorkflowRunResponse(
        workflow_id=final["workflow_id"],
        goal=final["goal"],
        status=final["status"],
        pending_task_id=final["pending_task_id"],
        tasks=final["tasks"],
        results=final["results"],
        logs=final["logs"],
    )