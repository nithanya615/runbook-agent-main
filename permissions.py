import os
"""
Enforces Role-Based Access Control (RBAC) permissions for the application.
"""

def can_execute_runbook(role: str) -> bool:
    """
    Checks if the role is allowed to execute runbooks.
    Only Developers are permitted to initiate runbook runs.
    Managers are restricted from directly running runbooks.
    """
    return role == "developer"

def can_approve_risky_action(role: str) -> bool:
    """
    Checks if the role is allowed to approve risky steps (e.g. restart services, cleanup).
    Only Managers are allowed to approve risky execution steps.
    Developers are restricted from approving risky steps.
    """
    return role == "manager"

def can_view_audit_logs(role: str) -> bool:
    """
    Checks if the role can view audit logs.
    Both Developer and Manager roles can view audit logs.
    """
    return role in ["developer", "manager"]

def can_view_active_users(role: str) -> bool:
    """
    Checks if the role can view the active users directory.
    Only Managers can view active users.
    """
    return role == "manager"

# ----------------------------------------------------
# SHARED RUNS AND APPROVAL SYNC
# ----------------------------------------------------
ACTIVE_RUNS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "active_runs.json")

def save_active_run(run_id: str, run_data: dict) -> None:
    """Saves active execution states in data/active_runs.json for multi-user sync."""
    import os
    import json
    os.makedirs(os.path.dirname(ACTIVE_RUNS_FILE), exist_ok=True)
    runs = {}
    if os.path.exists(ACTIVE_RUNS_FILE):
        try:
            with open(ACTIVE_RUNS_FILE, "r", encoding="utf-8") as f:
                runs = json.load(f)
        except Exception:
            runs = {}
    runs[run_id] = run_data
    try:
        with open(ACTIVE_RUNS_FILE, "w", encoding="utf-8") as f:
            json.dump(runs, f, indent=4)
    except Exception:
        pass

def load_active_run(run_id: str) -> dict:
    """Loads active execution state by ID."""
    import os
    import json
    if not os.path.exists(ACTIVE_RUNS_FILE):
        return {}
    try:
        with open(ACTIVE_RUNS_FILE, "r", encoding="utf-8") as f:
            runs = json.load(f)
        return runs.get(run_id, {})
    except Exception:
        return {}

def delete_active_run(run_id: str) -> None:
    """Deletes active execution state by ID after run completes."""
    import os
    import json
    if not os.path.exists(ACTIVE_RUNS_FILE):
        return
    try:
        with open(ACTIVE_RUNS_FILE, "r", encoding="utf-8") as f:
            runs = json.load(f)
        if run_id in runs:
            del runs[run_id]
        with open(ACTIVE_RUNS_FILE, "w", encoding="utf-8") as f:
            json.dump(runs, f, indent=4)
    except Exception:
        pass

def get_pending_runs() -> list:
    """Retrieves all active runs requiring manager approval."""
    import os
    import json
    if not os.path.exists(ACTIVE_RUNS_FILE):
        return []
    try:
        with open(ACTIVE_RUNS_FILE, "r", encoding="utf-8") as f:
            runs = json.load(f)
        return [r for r in runs.values() if r.get("status") == "NEEDS_APPROVAL"]
    except Exception:
        return []

