# AgentFlow AI - Agent Service (Developer 2)

FastAPI service that plans, executes, validates, recovers, risk-scores and remembers workflows.
Full API spec: `openapi.json` (or open `/docs` when the service is running).

## Run it locally
Requires Python 3.11.

```
cd python-ai
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
playwright install chromium    # optional, only needed for real browser tasks
copy .env.example .env         # Mac/Linux: cp .env.example .env
uvicorn app.main:app --port 8000
```
Set `SERVICE_API_KEY` in `.env` (default for dev: `agentflow-dev-key-123`).
Leave `OPENAI_API_KEY` empty to use demo mode (fixed plan, mock tools).

## Authentication
Every endpoint except `/health` needs the header `x-api-key: <SERVICE_API_KEY>`.

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | /agent/run | Run a whole workflow from a goal (main endpoint) |
| POST | /agent/plan | Planner only |
| POST | /agent/execute | Run one task |
| POST | /agent/validate | Validate one task's output |
| POST | /agent/recover | Ask the Recovery agent what to do about a failure |
| POST | /risk/analyze | Risk score 0-100 |
| POST | /memory/store | Store a memory |
| POST | /memory/search | Search memories |
| GET | /health | Health check |

## Main flow: POST /agent/run
Request: `{ "goal": "...", "user_id": "..." }`

The response `status` is one of:
- `completed`: everything ran. Show results.
- `awaiting_approval`: paused. `pending_task_id` is the task waiting for a human. Create an approval request.
- `escalated`: a task failed and recovery gave up. `pending_task_id` is the failing task. Show it as needing attention.
- `failed`: the workflow could not continue.

Other response fields: `tasks` (with status), `results`, `logs` (for the timeline), `validations`, `confidence`, `risks`, `recoveries`, `memories_used`.

### Approving a paused workflow
Store the whole response in your database while it waits. When the user approves, send it back:
```json
{
  "goal": "<same goal>",
  "user_id": "<same user>",
  "tasks": "<tasks from the response>",
  "results": "<results from the response>",
  "validations": "<validations from the response>",
  "risks": "<risks from the response>",
  "approved_tasks": ["<pending_task_id>"]
}
```
The workflow continues from where it paused. If the user rejects, just do not call it again and mark the workflow rejected.

### Example (Node.js)
```js
const res = await fetch(`${process.env.AI_URL}/agent/run`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "x-api-key": process.env.AI_API_KEY },
  body: JSON.stringify({ goal, user_id: userId }),
});
const run = await res.json();
```

### Suggested Socket.IO mapping
- `awaiting_approval` -> `approval-created`
- `completed` -> `workflow-completed`
- `failed` or `escalated` -> `workflow-failed`

## Demo helper
Add `"simulate_failures": {"gmail": "unavailable"}` (or `{"browser": "flaky"}`) to `/agent/run` to show self-healing.

## Notes
- Tools (Airtable, Gmail, Sheets) are mocks in this version. The API stays the same when real tools are added.
- Memories are stored per `user_id` in `data/memory.json`.