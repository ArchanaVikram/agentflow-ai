import re

from app.schemas import Task, ValidateRequest, ValidateResponse, ValidationCheck

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASS_THRESHOLD = 80  # confidence needed to pass


def _previous_output(context: dict, depends_on: list[str]) -> dict:
    for task_id in reversed(depends_on):
        if task_id in context:
            return context[task_id]
    return {}


def _check(name: str, passed: bool, detail: str) -> ValidationCheck:
    return ValidationCheck(name=name, passed=passed, detail=detail)


def _validate_browser(task: Task, output: dict, previous: dict) -> list[ValidationCheck]:
    if "startups" in output:
        startups = output["startups"]
        checks = [_check("Found results", len(startups) > 0, f"{len(startups)} startup(s) found")]
        text = f"{task.name} {task.description}".lower()
        if "email" in text or "contact" in text:
            with_email = [s for s in startups if s.get("email")]
            valid = [s for s in with_email if EMAIL_RE.match(s["email"])]
            checks.append(_check(
                "Emails collected",
                len(startups) > 0 and len(with_email) == len(startups),
                f"{len(with_email)} of {len(startups)} have an email",
            ))
            checks.append(_check(
                "Emails look valid",
                len(with_email) > 0 and len(valid) == len(with_email),
                f"{len(valid)} of {len(with_email)} emails are well-formed",
            ))
        return checks
    if "title" in output:
        return [_check("Page loaded", bool(output.get("title")), f"Page title: {output.get('title')}")]
    return [_check("Produced output", False, "The browser task returned nothing usable")]


def _validate_airtable(task: Task, output: dict, previous: dict) -> list[ValidationCheck]:
    expected = len(previous.get("startups", []))
    created = output.get("records_created", 0)
    return [
        _check("Records created", created > 0, f"{created} record(s) created"),
        _check("Record count matches input", created == expected, f"expected {expected}, created {created}"),
    ]


def _validate_gmail(task: Task, output: dict, previous: dict) -> list[ValidationCheck]:
    expected = len([s for s in previous.get("startups", []) if s.get("email")])
    sent = output.get("emails_sent", 0)
    recipients = output.get("recipients", [])
    valid = [r for r in recipients if EMAIL_RE.match(r)]
    return [
        _check("Emails sent", sent > 0, f"{sent} email(s) sent"),
        _check("Email count matches recipients", sent == expected, f"expected {expected}, sent {sent}"),
        _check("Recipient addresses valid", len(recipients) > 0 and len(valid) == len(recipients), f"{len(valid)} of {len(recipients)} valid"),
    ]


def _validate_sheets(task: Task, output: dict, previous: dict) -> list[ValidationCheck]:
    expected = len(previous.get("startups", []))
    written = output.get("rows_written", 0)
    return [
        _check("Rows written", written > 0, f"{written} row(s) written"),
        _check("Row count matches input", written == expected, f"expected {expected}, wrote {written}"),
    ]


def _validate_llm(task: Task, output: dict, previous: dict) -> list[ValidationCheck]:
    text = output.get("text", "")
    return [_check("Text generated", len(text.strip()) > 0, f"{len(text)} characters generated")]


HANDLERS = {
    "browser": _validate_browser,
    "airtable": _validate_airtable,
    "gmail": _validate_gmail,
    "sheets": _validate_sheets,
    "llm": _validate_llm,
}


def validate_task(req: ValidateRequest) -> ValidateResponse:
    previous = _previous_output(req.context, req.task.depends_on)
    checks = HANDLERS[req.task.tool](req.task, req.output, previous)
    passed_count = sum(1 for c in checks if c.passed)
    confidence = round(100 * passed_count / len(checks)) if checks else 0
    return ValidateResponse(
        workflow_id=req.workflow_id,
        task_id=req.task.id,
        passed=confidence >= PASS_THRESHOLD,
        confidence=confidence,
        checks=checks,
        summary=f"{passed_count} of {len(checks)} checks passed",
    )