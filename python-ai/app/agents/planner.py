import logging

from fastapi import HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings
from app.schemas import PlanRequest, PlanResponse, Task, ToolName

logger = logging.getLogger("planner")


# What we ask GPT-4o to return (every field is required)
class PlannedTask(BaseModel):
    id: str
    name: str
    description: str
    tool: ToolName
    depends_on: list[str]
    priority: int
    requires_approval: bool


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
"""


def _hints_text(hints: list[str] | None) -> str:
    if not hints:
        return ""
    lines = "\n".join(f"- {h}" for h in hints)
    return f"\n\nRelevant memory from past workflows and user preferences. Use it to plan better:\n{lines}\n"


def _demo_plan(req: PlanRequest) -> PlanResponse:
    """Used when there is no OpenAI key, so you can still test the API."""
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
    if not settings.openai_api_key:
        logger.warning("No OPENAI_API_KEY set - returning demo plan")
        return _demo_plan(req)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        completion = await client.beta.chat.completions.parse(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + _hints_text(hints)},
                {"role": "user", "content": req.goal},
            ],
            response_format=PlannerOutput,
        )
        output = completion.choices[0].message.parsed
    except Exception as e:
        logger.exception("Planner failed")
        raise HTTPException(status_code=502, detail=f"Planner failed: {e}")

    if output is None:
        raise HTTPException(status_code=502, detail="Planner returned no plan")

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