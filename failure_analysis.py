import os
import json
from datetime import datetime
from typing import List, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FAILURES_FILE = os.path.join(DATA_DIR, "failures.json")

def analyze_failure(step: str, command: str, returncode: int, stderr: str) -> Dict[str, Any]:
    """
    Analyzes a step execution failure and returns root cause analysis, severity, and recommendations.
    Saves the failure log entry to failures.json.
    
    Args:
        step (str): The name of the runbook step.
        command (str): The command executed.
        returncode (int): The return code from the subprocess.
        stderr (str): The standard error capture from the execution.
        
    Returns:
        dict: Recovery recommendation dict containing:
            {
                "failure": str,
                "root_cause": str,
                "recommendation": str,
                "severity": "LOW" | "MEDIUM" | "HIGH"
            }
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 1. Determine Root Cause, Recommendation, and Severity dynamically
    root_cause = "Subprocess execution returned a non-zero exit code."
    recommendation = "Check execution permissions, verify executable path, and ensure arguments are valid."
    severity = "LOW"
    
    cmd_lower = command.lower() if command else ""
    stderr_lower = stderr.lower() if stderr else ""
    
    if "df" in cmd_lower or "free" in cmd_lower:
        root_cause = "Linux utility (df/free) is not available or executable on the target operating system (e.g. running on Windows)."
        recommendation = "Verify command availability. Install compatible tools (such as Git Bash, Cygwin, or WSL) or modify the runbook command map for local OS compatibility."
        severity = "MEDIUM"
    elif "systemctl" in cmd_lower or "service" in cmd_lower:
        root_cause = "The Nginx or target daemon service command failed or is not available (systemd manager is not running on this host)."
        recommendation = "Ensure the service is installed. On Windows, use Powershell commands like 'Restart-Service nginx'. On non-systemd Linux hosts, try 'service nginx restart'."
        severity = "HIGH"
    elif "not recognized" in stderr_lower or "file not found" in stderr_lower or "no such file" in stderr_lower:
        root_cause = "Target executable or utility is missing or not declared in the system PATH env variable."
        recommendation = "Install the missing dependency, check command spelling, or declare the full absolute executable path."
        severity = "HIGH"
    elif "permission denied" in stderr_lower or "access denied" in stderr_lower:
        root_cause = "The current agent process lacks sufficient administrative privileges to run this command."
        recommendation = "Ensure the agent is running under root/administrator privileges, or prepend command with 'sudo'."
        severity = "HIGH"
    elif returncode == -2:
        root_cause = "Command execution timed out after the safety timeout threshold (10 seconds)."
        recommendation = "Check if the command is running interactively or waiting for user prompt, and optimize execution speed."
        severity = "MEDIUM"
        
    analysis_report = {
        "failure": f"{step} (command: '{command}') failed with return code {returncode}.",
        "root_cause": root_cause,
        "recommendation": recommendation,
        "severity": severity,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stderr": stderr if stderr else "No error output captured."
    }
    
    # Save failure to database
    failures = []
    if os.path.exists(FAILURES_FILE):
        try:
            with open(FAILURES_FILE, "r", encoding="utf-8") as f:
                failures = json.load(f)
        except Exception:
            failures = []
            
    failures.append(analysis_report)
    
    try:
        with open(FAILURES_FILE, "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=4)
    except Exception:
        pass
        
    return {
        "failure": analysis_report["failure"],
        "root_cause": analysis_report["root_cause"],
        "recommendation": analysis_report["recommendation"],
        "severity": analysis_report["severity"]
    }

def get_failures() -> List[Dict[str, Any]]:
    """
    Retrieves the list of all recorded execution failures.
    
    Returns:
        list: List of failure analysis dictionaries.
    """
    if not os.path.exists(FAILURES_FILE):
        return []
        
    try:
        with open(FAILURES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
