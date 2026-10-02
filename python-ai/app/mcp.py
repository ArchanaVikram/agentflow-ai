import json
import threading
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

# Permissions are saved in python-ai/data/mcp_permissions.json
PERMISSIONS_FILE = Path(__file__).resolve().parent.parent / "data" / "mcp_permissions.json"
_lock = threading.Lock()


class McpAction(BaseModel):
    name: str
    description: str
    risk: str  # SAFE / MEDIUM / HIGH


class McpTool(BaseModel):
    id: str
    name: str
    description: str
    category: str
    status: str  # live = real, mock = simulated in this version, planned = not built yet
    executable: bool  # can the Executor run tasks with this tool today?
    can_disable: bool
    actions: list[McpAction]
    enabled: bool = True


class McpToolsResponse(BaseModel):
    tools: list[McpTool]


class McpPermissionRequest(BaseModel):
    tool: str
    enabled: bool


def _tool(tool_id, name, description, category, status, executable, actions, can_disable=True) -> McpTool:
    return McpTool(
        id=tool_id,
        name=name,
        description=description,
        category=category,
        status=status,
        executable=executable,
        can_disable=can_disable,
        actions=[McpAction(name=n, description=d, risk=r) for n, d, r in actions],
    )


REGISTRY: dict[str, McpTool] = {
    t.id: t
    for t in [
        _tool("browser", "Browser", "Opens websites and extracts data (Playwright)", "web", "live", True,
              [("open_page", "Open a web page", "SAFE"), ("extract_data", "Extract text and emails from a page", "SAFE")],
              can_disable=False),
        _tool("llm", "Language model", "Writes, summarises and analyses text", "ai", "live", True,
              [("generate_text", "Generate text from instructions and data", "SAFE")],
              can_disable=False),
        _tool("gmail", "Gmail", "Read and send email with Gmail", "email", "mock", True,
              [("search_email", "Search the inbox", "SAFE"), ("send_email", "Send an email", "MEDIUM")]),
        _tool("outlook", "Outlook", "Read and send email with Outlook (backup for Gmail)", "email", "mock", True,
              [("search_email", "Search the inbox", "SAFE"), ("send_email", "Send an email", "MEDIUM")]),
        _tool("airtable", "Airtable", "Store and read records in Airtable bases", "database", "mock", True,
              [("read_records", "Read records", "SAFE"), ("create_records", "Create records", "MEDIUM"),
               ("update_records", "Update records", "MEDIUM")]),
        _tool("sheets", "Google Sheets", "Read and write spreadsheet rows", "spreadsheet", "mock", True,
              [("read_rows", "Read rows", "SAFE"), ("append_rows", "Append rows", "MEDIUM")]),
        _tool("slack", "Slack", "Post messages and read channels", "chat", "planned", False,
              [("read_channel", "Read a channel", "SAFE"), ("post_message", "Post a message", "MEDIUM")]),
        _tool("notion", "Notion", "Search and create pages", "docs", "planned", False,
              [("search_pages", "Search pages", "SAFE"), ("create_page", "Create a page", "MEDIUM")]),
        _tool("hubspot", "HubSpot", "Manage CRM contacts and deals", "crm", "planned", False,
              [("read_contacts", "Read contacts", "SAFE"), ("create_contact", "Create a contact", "MEDIUM"),
               ("update_deal", "Update a deal", "MEDIUM")]),
        _tool("salesforce", "Salesforce", "Manage CRM leads and accounts", "crm", "planned", False,
              [("read_leads", "Read leads", "SAFE"), ("update_lead", "Update a lead", "MEDIUM")]),
    ]
}


def _load_permissions() -> dict:
    if not PERMISSIONS_FILE.exists():
        return {}
    try:
        return json.loads(PERMISSIONS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def is_enabled(tool_id: str) -> bool:
    tool = REGISTRY.get(tool_id)
    if tool is None or not tool.can_disable:
        return True
    return _load_permissions().get(tool_id, True)


def list_tools(search: Optional[str] = None) -> list[McpTool]:
    permissions = _load_permissions()
    tools = []
    for tool in REGISTRY.values():
        enabled = permissions.get(tool.id, True) if tool.can_disable else True
        item = tool.model_copy(update={"enabled": enabled})
        if search:
            actions_text = " ".join(f"{a.name} {a.description}" for a in item.actions)
            haystack = f"{item.id} {item.name} {item.description} {item.category} {actions_text}".lower()
            if not any(word in haystack for word in search.lower().split()):
                continue
        tools.append(item)
    return tools


def set_permission(tool_id: str, enabled: bool) -> McpTool:
    tool = REGISTRY.get(tool_id)
    if tool is None:
        raise KeyError(tool_id)
    if not tool.can_disable:
        raise ValueError(f"'{tool_id}' is a built-in tool and cannot be switched off")
    with _lock:
        permissions = _load_permissions()
        permissions[tool_id] = enabled
        PERMISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PERMISSIONS_FILE.write_text(json.dumps(permissions), encoding="utf-8")
    return tool.model_copy(update={"enabled": enabled})