import json
import logging

from fastapi import HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.schemas import PlanRequest, PlanResponse, Task, ToolName

logger = logging.getLogger("planner")


class PlannedTask(BaseModel):
    id: str
    name: str
    description: str
    tool: ToolName
    depends_on: list[str] = []
    priority: int = 1
    requires_approval: bool = False


class PlannerOutput(BaseModel):
    intent: str
    tasks: list[PlannedTask]


SYSTEM_PROMPT = """You are the Planner Agent of an autonomous automation platform.
Turn the user's goal into a short, ordered list of concrete tasks (3 to 8 tasks).

Available tools:
- browser: search the web, visit websites, extract data
- airtable: store or read records in Airtable
- sheets: read or write Google Sheets
- gmail: send or read emails
- outlook: send or read emails (backup for gmail)
- llm: writing, summarising or analysing text

Rules:
- Task ids are "t1", "t2", "t3", ...
- depends_on lists ids of tasks that must finish first.
- priority 1 is the most urgent; higher numbers run later.
- Set requires_approval to true for any task that sends emails, messages or payments, or deletes or bulk-changes data.
- "intent" is one short sentence describing what the user wants.

Reply with ONLY a JSON object (no markdown, no explanation) in exactly this shape:
{"intent": "...", "tasks": [{"id": "t1", "name": "...", "description": "...", "tool": "browser", "depends_on": [], "priority": 1, "requires_approval": false}]}
"tool" must be one of: browser, airtable, gmail, outlook, sheets, llm.
"""


def _hints_text(hints: list[str] | None) -> str:
    if not hints:
        return ""
    lines = "\n".join(f"- {h}" for h in hints)
    return f"\n\nRelevant memory from past workflows and user preferences. Use it to plan better:\n{lines}\n"


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in the model reply")
    return json.loads(text[start : end + 1])


def _demo_plan(req: PlanRequest) -> PlanResponse:
    """Used when there is no LLM key, so you can still test the API."""
    return PlanResponse(
        workflow_id=req.workflow_id,
        goal=req.goal,
        intent="Find companies, store them in a database and contact them (demo plan)",
        tasks=[
            Task(id="t1", name="Search AI startups", description="Search the web for AI startups in the target city", tool="browser", priority=1),
            Task(id="t2", name="Collect contact emails", description="Visit each startup website and extract contact emails", tool="browser", depends_on=["t1"], priority=2),
            Task(id="t3", name="Store data in Airtable", description="Save startup names, websites and emails as Airtable records", tool="airtable", depends_on=["t2"], priority=3),
            Task(id="t4", name="Send outreach emails", description="Send a personalised outreach email to each startup", tool="gmail", depends_on=["t3"], priority=4, requires_approval=True),
        ],
    )


async def create_plan(req: PlanRequest, hints: list[str] | None = None) -> PlanResponse:
    if not settings.llm_api_key:
        logger.warning("No LLM_API_KEY set - returning demo plan")
        return _demo_plan(req)

    client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url or None)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + _hints_text(hints)},
        {"role": "user", "content": req.goal},
    ]

    output: PlannerOutput | None = None
    last_error: Exception | None = None
    content = ""
    for _ in range(2):  # one retry if the reply is malformed
        try:
            completion = await client.chat.completions.create(
                model=settings.llm_model, messages=messages, temperature=0.2
            )
            content = completion.choices[0].message.content or ""
            output = PlannerOutput.model_validate(_extract_json(content))
            ids = [t.id for t in output.tasks]
            if not ids or len(set(ids)) != len(ids):
                raise ValueError("Task ids must be unique")
            if any(d not in ids for t in output.tasks for d in t.depends_on):
                raise ValueError("depends_on refers to a task that does not exist")
            break
        except (ValueError, ValidationError) as e:  # bad JSON or bad plan: ask again
            last_error = e
            output = None
            messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"That reply was not valid ({e}). Reply again with ONLY the JSON object."},
            ]
        except Exception as e:  # network, key, model name, rate limit...
            logger.exception("Planner failed")
            raise HTTPException(status_code=502, detail=f"Planner failed: {e}")

    if output is None:
        raise HTTPException(status_code=502, detail=f"Planner returned an invalid plan: {last_error}")

    tasks = []
    for t in output.tasks:
        task = Task(**t.model_dump())
        if task.tool in ("gmail", "outlook"):  # safety rule: emails always need approval
            task.requires_approval = True
        tasks.append(task)

    return PlanResponse(
        workflow_id=req.workflow_id,
        goal=req.goal,
        intent=output.intent,
        tasks=tasks,
    )