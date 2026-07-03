import os
import json
from typing import List, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

ANNOTATION_FILE = os.path.join(DATA_DIR, "audit_annotations.json")

# ----------------------------------------------------
# AUDIT ANNOTATIONS DATABASE
# ----------------------------------------------------
def load_audit_annotations() -> Dict[str, List[Dict[str, str]]]:
    if not os.path.exists(ANNOTATION_FILE):
        return {}
    try:
        with open(ANNOTATION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure proper format Dict[str, List[Dict]]
            if isinstance(data, dict):
                # Basic validation to prevent crash if old format
                if any(isinstance(v, str) for v in data.values()):
                    return {}
                return data
            return {}
    except Exception:
        return {}

def save_audit_annotations(annotations: Dict[str, List[Dict[str, str]]]):
    with open(ANNOTATION_FILE, "w", encoding="utf-8") as f:
        json.dump(annotations, f, indent=4)

def update_audit_comment(log_key: str, user: str, comment: str, timestamp: str):
    annotations = load_audit_annotations()
    if log_key not in annotations:
        annotations[log_key] = []
    
    annotations[log_key].append({
        "username": user,
        "timestamp": timestamp,
        "comment": comment
    })
    
    save_audit_annotations(annotations)
