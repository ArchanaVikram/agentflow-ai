from app.schemas import RiskRequest, RiskResponse

# (score, keywords, reason) - checked from most to least dangerous
RULES = [
    (95, ["delete", "drop", "wipe", "truncate", "remove all", "destroy"], "Destructive action that may cause permanent data loss"),
    (90, ["payment", "transfer money", "purchase", "refund", "invoice", "wire "], "Financial transaction"),
    (80, ["bulk", "mass ", "all contacts", "every customer", "blast"], "Bulk operation affecting many records"),
]
EMAIL_TOOLS = ["gmail", "outlook"]
WRITE_WORDS = ["update", "store", "write", "create", "insert", "save", "crm", "modify"]


def analyze_risk(req: RiskRequest) -> RiskResponse:
    text = f"{req.action} {req.tool or ''}".lower()
    score, reason = 5, "Read-only action"

    for rule_score, words, rule_reason in RULES:
        if any(w in text for w in words):
            score, reason = rule_score, rule_reason
            break
    else:
        if req.tool in EMAIL_TOOLS or ("send" in text and ("email" in text or "message" in text)):
            score, reason = 60, "Sends external communication that cannot be undone"
        elif any(w in text for w in WRITE_WORDS):
            score, reason = 40, "Modifies data in an external system"

    if score >= 70:
        level = "HIGH"
    elif score >= 30:
        level = "MEDIUM"
    else:
        level = "SAFE"

    return RiskResponse(
        score=score,
        level=level,
        requires_approval=score >= 50,
        reason=reason,
    )