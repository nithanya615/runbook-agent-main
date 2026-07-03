import os
import json
from datetime import datetime
from typing import List, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ACTIVE_USERS_FILE = os.path.join(DATA_DIR, "active_users.json")

def track_user_activity(username: str, role: str) -> None:
    """
    Updates or inserts a user session into the active users database.
    
    Args:
        username (str): Logged-in username.
        role (str): Role of the user.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    users_data = {}
    if os.path.exists(ACTIVE_USERS_FILE):
        try:
            with open(ACTIVE_USERS_FILE, "r", encoding="utf-8") as f:
                users_data = json.load(f)
        except Exception:
            users_data = {}
            
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if username in users_data:
        users_data[username]["last_activity"] = now_str
    else:
        users_data[username] = {
            "username": username,
            "role": role,
            "login_time": now_str,
            "last_activity": now_str
        }
        
    try:
        with open(ACTIVE_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4)
    except Exception:
        pass

def remove_active_user(username: str) -> None:
    """
    Removes a user session from the active users registry (e.g. on logout).
    
    Args:
        username (str): The username to remove.
    """
    if not os.path.exists(ACTIVE_USERS_FILE):
        return
        
    try:
        with open(ACTIVE_USERS_FILE, "r", encoding="utf-8") as f:
            users_data = json.load(f)
        if username in users_data:
            del users_data[username]
        with open(ACTIVE_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4)
    except Exception:
        pass

def get_active_users() -> List[Dict[str, Any]]:
    """
    Retrieves the list of active user sessions.
    
    Returns:
        list: List of dictionaries of active users.
    """
    if not os.path.exists(ACTIVE_USERS_FILE):
        return []
        
    try:
        with open(ACTIVE_USERS_FILE, "r", encoding="utf-8") as f:
            users_data = json.load(f)
        return list(users_data.values())
    except Exception:
        return []
