from app.schemas import RecoverRequest, RecoverResponse

# If a tool is down, which tool can do the same job?
ALTERNATES = {"gmail": "outlook", "outlook": "gmail"}

UNAVAILABLE = ["unavailable", "503", "502", "connection refused", "unauthorized", "401", "403"]
TRANSIENT = ["timeout", "timed out", "rate limit", "429", "temporar"]
ELEMENT = ["selector", "element", "not found"]


def _has(error: str, words: list[str]) -> bool:
    return any(w in error for w in words)


def decide_recovery(req: RecoverRequest) -> RecoverResponse:
    error = req.error.lower()
    tool = req.task.tool
    alternative = ALTERNATES.get(tool)

    def reply(action: str, reason: str, new_tool: str | None = None) -> RecoverResponse:
        return RecoverResponse(task_id=req.task.id, action=action, new_tool=new_tool, reason=reason)

    if error.startswith("validation failed"):
        if req.attempt == 1:
            return reply("retry", "Result did not pass validation, trying once more")
        return reply("escalate", "Result still fails validation - human review needed")

    if _has(error, UNAVAILABLE):
        if alternative and req.attempt == 1:
            return reply("switch_tool", f"{tool} is unavailable, switching to {alternative}", alternative)
        return reply("escalate", f"{tool} is unavailable and no working alternative - human help needed")

    if _has(error, TRANSIENT):
        if req.attempt <= 2:
            return reply("retry", f"Temporary problem with {tool}, retrying (attempt {req.attempt} of 2)")
        return reply("escalate", f"{tool} keeps timing out - human help needed")

    if _has(error, ELEMENT):
        if req.attempt == 1:
            return reply("retry", "Page element missing - re-analysing the page and retrying")
        return reply("escalate", "Page element still missing - the website may have changed")

    return reply("escalate", "Unknown error - human help needed")