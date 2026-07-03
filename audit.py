import os
import json
from datetime import datetime
from typing import List, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
AUDIT_LOG_FILE = os.path.join(DATA_DIR, "audit_logs.json")

def write_audit_log(user: str, role: str, action: str, step: str = None, status: str = None, details: str = None) -> None:
    """
    Writes a new entry to the audit logs JSON file.
    
    Args:
        user (str): The username performing the action.
        role (str): The role of the user.
        action (str): The action keyword (e.g. LOGIN, LOGOUT, EXECUTE_RUNBOOK, EXECUTE_STEP, etc.)
        step (str, optional): The name of the runbook step.
        status (str, optional): The execution status (e.g. SUCCESS, FAILED, BLOCKED, etc.)
        details (str, optional): Extra description details.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user,
        "role": role,
        "action": action,
        "step": step if step else "N/A",
        "status": status if status else "N/A",
        "details": details if details else ""
    }
    
    logs = []
    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
            
    logs.append(log_entry)
    
    try:
        with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4)
    except Exception:
        pass

def read_audit_logs() -> List[Dict[str, Any]]:
    """
    Reads all audit logs from the JSON database.
    
    Returns:
        list: A list of audit log dictionaries.
    """
    if not os.path.exists(AUDIT_LOG_FILE):
        return []
        
    try:
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
