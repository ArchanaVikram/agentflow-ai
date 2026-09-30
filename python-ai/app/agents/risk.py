from app.schemas import RiskRequest, RiskResponse


def analyze_risk(req: RiskRequest) -> RiskResponse:
    text = f"{req.action} {req.tool or ''}".lower()

    if any(w in text for w in ["delete", "drop", "wipe", "remove all"]):
        score, reason = 95, "Destructive action that may cause data loss"
    elif any(w in text for w in ["payment", "transfer", "purchase", "refund"]):
        score, reason = 90, "Financial transaction"
    elif any(w in text for w in ["bulk", "mass", "all contacts"]):
        score, reason = 80, "Bulk operation affecting many records"
    elif req.tool == "gmail" or ("send" in text and ("email" in text or "message" in text)):
        score, reason = 60, "Sends external communication that cannot be undone"
    elif any(w in text for w in ["update", "store", "write", "create", "insert", "crm"]):
        score, reason = 40, "Modifies data in an external system"
    else:
        score, reason = 5, "Read-only action"

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