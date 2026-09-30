import logging

from app.agents.browser_tool import URL_PATTERN, read_page
from app.config import settings
from app.schemas import ExecuteRequest, ExecuteResponse, Task

logger = logging.getLogger("executor")

# Fake data for demo mode (example.com emails are never real)
DEMO_STARTUPS = [
    {"name": "Demo AI Labs", "website": "https://demoailabs.example.com", "email": "hello@demoailabs.example.com"},
    {"name": "Sample Neural Works", "website": "https://sampleneural.example.com", "email": "contact@sampleneural.example.com"},
    {"name": "Test Vision Systems", "website": "https://testvision.example.com", "email": "team@testvision.example.com"},
]


def _previous_output(context: dict, depends_on: list[str]) -> dict:
    """Find the output of the most recent earlier task this task depends on."""
    for task_id in reversed(depends_on):
        if task_id in context:
            return context[task_id]
    return {}


async def _browser(task: Task, context: dict, logs: list[str]) -> dict:
    match = URL_PATTERN.search(f"{task.name} {task.description}")
    if match and settings.real_browser:
        return await read_page(match.group(0), logs)

    text = f"{task.name} {task.description}".lower()
    if "email" in text or "contact" in text:
        previous = _previous_output(context, task.depends_on)
        names = {s["name"] for s in previous.get("startups", [])}
        found = [s for s in DEMO_STARTUPS if s["name"] in names]
        logs.append(f"Visited {len(found)} websites and extracted contact emails")
        return {"startups": found}
    logs.append("Searched the web for AI startups")
    return {"startups": [{"name": s["name"], "website": s["website"]} for s in DEMO_STARTUPS]}


async def _airtable(task: Task, context: dict, logs: list[str]) -> dict:
    startups = _previous_output(context, task.depends_on).get("startups", [])
    logs.append(f"Saved {len(startups)} records to Airtable (mock)")
    return {"records_created": len(startups), "startups": startups}


async def _gmail(task: Task, context: dict, logs: list[str]) -> dict:
    startups = _previous_output(context, task.depends_on).get("startups", [])
    recipients = [s["email"] for s in startups if s.get("email")]
    logs.append(f"Sent {len(recipients)} outreach emails (mock)")
    return {"emails_sent": len(recipients), "recipients": recipients}


async def _outlook(task: Task, context: dict, logs: list[str]) -> dict:
    result = await _gmail(task, context, logs)
    logs[-1] = logs[-1].replace("(mock)", "via Outlook (mock)")
    return result


async def _sheets(task: Task, context: dict, logs: list[str]) -> dict:
    startups = _previous_output(context, task.depends_on).get("startups", [])
    logs.append(f"Wrote {len(startups)} rows to Google Sheets (mock)")
    return {"rows_written": len(startups)}


async def _llm(task: Task, context: dict, logs: list[str]) -> dict:
    logs.append("Generated text with the language model (mock)")
    return {"text": f"Mock result for: {task.name}"}


TOOLS = {
    "browser": _browser,
    "airtable": _airtable,
    "gmail": _gmail,
    "outlook": _outlook,
    "sheets": _sheets,
    "llm": _llm,
}


async def execute_task(req: ExecuteRequest) -> ExecuteResponse:
    task = req.task
    logs = [f"Executor started task {task.id}: {task.name} (tool: {task.tool})"]

    # Human-in-the-loop: risky tasks wait for approval
    if task.requires_approval and not req.approved:
        logs.append("Waiting for human approval before running")
        return ExecuteResponse(
            workflow_id=req.workflow_id,
            task_id=task.id,
            status="awaiting_approval",
            logs=logs,
        )

    if not settings.mock_tools:
        return ExecuteResponse(
            workflow_id=req.workflow_id,
            task_id=task.id,
            status="failed",
            logs=logs,
            error="Real tools are not implemented yet",
        )

    try:
        # Demo helper: pretend the tool is broken
        if req.simulate_failure == "unavailable":
            raise RuntimeError(f"503 Service unavailable: {task.tool}")
        if req.simulate_failure == "flaky":
            raise RuntimeError(f"Timeout while contacting {task.tool}")

        output = await TOOLS[task.tool](task, req.context, logs)
        logs.append(f"Task {task.id} completed")
        return ExecuteResponse(
            workflow_id=req.workflow_id,
            task_id=task.id,
            status="completed",
            output=output,
            logs=logs,
        )
    except Exception as e:
        logger.exception("Task %s failed", task.id)
        logs.append(f"Task {task.id} failed: {e}")
        return ExecuteResponse(
            workflow_id=req.workflow_id,
            task_id=task.id,
            status="failed",
            logs=logs,
            error=str(e),
        )