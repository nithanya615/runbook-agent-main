import os
import json
from datetime import datetime
from typing import List, Dict, Any

def generate_report(
    runbook_title: str,
    results: List[Dict[str, Any]],
    user: str = "unknown",
    role: str = "unknown",
    timeline: List[str] = None,
    audit_trail: List[Dict[str, Any]] = None,
    failures: List[Dict[str, Any]] = None,
    recommendations: List[Dict[str, Any]] = None
) -> str:
    """
    Generates an enhanced incident response execution report and saves it as a JSON file.
    
    Args:
        runbook_title (str): Title of the runbook that was executed.
        results (list): Execution outcomes of each step.
        user (str, optional): Username of the operator.
        role (str, optional): Role of the operator.
        timeline (list, optional): Incident events chronological timeline.
        audit_trail (list, optional): Audit logs recorded during this session.
        failures (list, optional): Diagnostic reports of any failed steps.
        recommendations (list, optional): Generated recovery advice.
        
    Returns:
        str: Absolute file path of the saved JSON report.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    reports_dir = os.path.join(base_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    # Calculate summary counts
    total = len(results)
    success = sum(1 for r in results if r.get("status") == "SUCCESS")
    failed = sum(1 for r in results if r.get("status") == "FAILED")
    skipped = sum(1 for r in results if r.get("status") == "SKIPPED")
    blocked = sum(1 for r in results if r.get("status") == "BLOCKED")
    
    iso_now = datetime.now().isoformat()
    filename_now = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    report_data = {
        "runbook": runbook_title,
        "timestamp": iso_now,
        "operator": {
            "user": user,
            "role": role
        },
        "summary": {
            "total": total,
            "success": success,
            "failed": failed,
            "skipped": skipped,
            "blocked": blocked
        },
        "results": results,
        "timeline": timeline if timeline else [],
        "audit_trail": audit_trail if audit_trail else [],
        "failures": failures if failures else [],
        "recommendations": recommendations if recommendations else []
    }
    
    filename = f"execution_report_{filename_now}.json"
    file_path = os.path.join(reports_dir, filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=4)
        
    return file_path
