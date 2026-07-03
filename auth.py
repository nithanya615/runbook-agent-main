import os
import json
import bcrypt
from typing import Dict, Any, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

def initialize_users() -> None:
    """
    Initializes the users database file if it does not exist.
    Pre-populates it with default developer and manager users with bcrypt hashed passwords.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        default_users = {
            "developer": {
                "password_hash": bcrypt.hashpw("dev123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
                "role": "developer"
            },
            "manager": {
                "password_hash": bcrypt.hashpw("mgr123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
                "role": "manager"
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4)

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticates a user against the users database using bcrypt.
    
    Args:
        username (str): The username.
        password (str): The plain-text password.
        
    Returns:
        dict: User metadata dictionary containing role if successful, else None.
    """
    initialize_users()
    if not os.path.exists(USERS_FILE):
        return None
        
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users_data = json.load(f)
    except Exception:
        return None
        
    if username in users_data:
        user_info = users_data[username]
        pw_hash_str = user_info.get("password_hash", "")
        # Verify the password using bcrypt
        try:
            if bcrypt.checkpw(password.encode('utf-8'), pw_hash_str.encode('utf-8')):
                return {
                    "username": username,
                    "role": user_info.get("role", "developer")
                }
        except Exception:
            return None
            
    return None

def register_user(username: str, password: str, role: str) -> bool:
    """
    Registers a new user in the users database.
    
    Args:
        username (str): The username.
        password (str): The plain-text password.
        role (str): The role ('developer' or 'manager').
        
    Returns:
        bool: True if registration is successful, False if user already exists.
    """
    initialize_users()
    if not os.path.exists(USERS_FILE):
        return False
        
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users_data = json.load(f)
    except Exception:
        users_data = {}
        
    if username in users_data:
        return False  # Already exists
        
    # Generate bcrypt hash
    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    users_data[username] = {
        "password_hash": pw_hash,
        "role": role
    }
    
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4)
        return True
    except Exception:
        return False
