import subprocess
from typing import Dict, Any

# Map of runbook step names to safe mock commands (default fallback commands)
COMMAND_MAP: Dict[str, str] = {
    "Check disk space": "df -h",
    "Check memory usage": "free -m",
    "Check current Nginx status": "echo nginx status: active (running)",
    "Review recent Nginx logs": "echo log: no critical errors found",
    "Restart Nginx service": "echo nginx restarted successfully",
    "Verify Nginx service status": "echo nginx status: active (running)",
    "Verify application health endpoint": "echo HTTP 200 OK - application healthy",
    "Check CPU usage": "echo CPU usage: 23%",
    "Identify top CPU-consuming processes": "echo top process: python3 (12%), nginx (8%)",
    "Check system load": "echo system load: 0.45 0.38 0.32",
    "Restart affected service": "echo service restarted successfully",
    "Verify CPU usage has decreased": "echo CPU usage: 11% - within normal range",
    "Check disk usage": "df -h",
    "Identify large files": "echo large files: /var/log/app.log (2.1GB)",
    "Review log directory size": "echo /var/log total: 3.4GB",
    "Clean temporary files": "echo cleaned 1.2GB from /tmp",
    "Verify available disk space": "echo disk usage: 45% - healthy"
}

# Steps that present potential risk and require explicit operator confirmation
RISKY_STEPS = ["Restart Nginx service", "Restart affected service", "Clean temporary files"]

def _run_subprocess(command: str) -> Dict[str, Any]:
    """
    Executes a shell command by communicating with our custom stdio MCP server 
    using JSON-RPC over stdin/stdout.
    """
    import sys
    import json
    import os
    
    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")
    
    try:
        # Spawn the custom stdio MCP server
        process = subprocess.Popen(
            [sys.executable, server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # 1. Send initialize request to establish MCP session
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "runbook-client", "version": "1.0"}
            }
        }
        process.stdin.write(json.dumps(init_req) + "\n")
        process.stdin.flush()
        
        # Read server initialization response
        init_res = json.loads(process.stdout.readline())
        
        # 2. Send initialized notification (required by MCP spec)
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        process.stdin.write(json.dumps(initialized_notification) + "\n")
        process.stdin.flush()
        
        # 3. Call execute_command tool on MCP server
        call_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "execute_command",
                "arguments": {
                    "command": command
                }
            }
        }
        process.stdin.write(json.dumps(call_req) + "\n")
        process.stdin.flush()
        
        # Read command execution result from server
        call_res = json.loads(process.stdout.readline())
        
        # Clean shutdown of MCP process
        process.stdin.close()
        process.terminate()
        process.wait()
        
        result = call_res.get("result", {})
        content_list = result.get("content", [])
        text_output = content_list[0].get("text", "") if content_list else "No output"
        is_error = result.get("isError", False)
        returncode = result.get("returncode", 0)
        
        return {
            "status": "FAILED" if is_error else "SUCCESS",
            "output": text_output,
            "returncode": returncode
        }
        
    except Exception as e:
        return {
            "status": "FAILED",
            "output": f"MCP tool execution failed: {str(e)}",
            "returncode": -1
        }

def validate_command_safety(command: str) -> bool:
    """
    Dynamically validates command safety.
    Returns False if the command contains any dangerous destructive keywords.
    """
    blocked_keywords = [
        "rm ", "del ", "format", "mkfs", "dd ", "shred",
        "drop database", "truncate", "shutdown", "reboot"
    ]
    cmd_lower = command.strip().lower()
    for kw in blocked_keywords:
        if kw in cmd_lower:
            return False
    return True

def execute_step(step: str, command: str = None) -> Dict[str, Any]:
    """
    Looks up a step and executes its command. If a command is passed explicitly,
    that command is used. Otherwise, it falls back to COMMAND_MAP.
    Checks command safety using a dynamic blocklist and flags risky steps for approval.
    
    Args:
        step (str): The name of the runbook step.
        command (str, optional): The command to execute (e.g. parsed from Markdown).
        
    Returns:
        dict: Result metadata including step, command, status, output, and returncode.
    """

    if not command:
        if step not in COMMAND_MAP:
            return {
                "step": step,
                "status": "BLOCKED",
                "output": "Command not mapped",
                "returncode": -1
            }
        command = COMMAND_MAP[step]
    else:
        if command not in COMMAND_MAP.values():
            return {
                "step": step,
                "command": command,
                "status": "BLOCKED",
                "output": f"Command '{command}' is not in the allowed command map.",
                "returncode": -1
            }
        
    # Security verification (Dynamic safety engine)
    if not validate_command_safety(command):
        return {
            "step": step,
            "command": command,
            "status": "BLOCKED",
            "output": f"Security Alert: Command '{command}' was blocked. It contains destructive keywords.",
            "returncode": -1
        }
        
    # Dynamic risk assessment: check static lists and risk keywords (case-insensitive)
    is_risky = step in RISKY_STEPS or any(word in step.lower() for word in ["restart", "clean", "delete", "remove", "stop"])
    
    if is_risky:
        return {
            "step": step,
            "command": command,
            "status": "NEEDS_APPROVAL",
            "output": f"Step '{step}' is marked risky. Operator confirmation is required.",
            "returncode": -1
        }
        
    res = _run_subprocess(command)
    return {
        "step": step,
        "command": command,
        "status": res["status"],
        "output": res["output"],
        "returncode": res["returncode"]
    }

def force_execute_step(step: str, command: str = None) -> Dict[str, Any]:
    """
    Executes a step bypassing the risky step validation check.
    If a command is passed explicitly, it executes that command instead of COMMAND_MAP.
    
    Args:
        step (str): The name of the runbook step.
        command (str, optional): The command to execute.
        
    Returns:
        dict: Result metadata including step, command, status, output, and returncode.
    """

    if not command:
        if step not in COMMAND_MAP:
            return {
                "step": step,
                "status": "BLOCKED",
                "output": "Command not mapped",
                "returncode": -1
            }
        command = COMMAND_MAP[step]
    else:
        if command not in COMMAND_MAP.values():
            return {
                "step": step,
                "command": command,
                "status": "BLOCKED",
                "output": f"Command '{command}' is not in the allowed command map.",
                "returncode": -1
            }
        
    # Security verification still applies even when forced
    if not validate_command_safety(command):
        return {
            "step": step,
            "command": command,
            "status": "BLOCKED",
            "output": f"Security Alert: Command '{command}' was blocked. It contains destructive keywords.",
            "returncode": -1
        }
        
    res = _run_subprocess(command)
    return {
        "step": step,
        "command": command,
        "status": res["status"],
        "output": res["output"],
        "returncode": res["returncode"]
    }
