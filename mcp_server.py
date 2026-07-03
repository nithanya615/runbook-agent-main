import sys
import json
import subprocess

def log(msg):
    sys.stderr.write(f"[Server Log] {msg}\n")
    sys.stderr.flush()

def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            req_id = request.get("id")
            method = request.get("method")
            
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "custom-mcp-shell-server",
                            "version": "1.0.0"
                        }
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "execute_command",
                                "description": "Executes shell commands safely.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "command": {"type": "string"}
                                    },
                                    "required": ["command"]
                                }
                            }
                        ]
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                
            elif method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name == "execute_command":
                    cmd = arguments.get("command", "")
                    
                    import re
                    # Strict allowlist of safe commands
                    ALLOWLIST = [
                        r"^df\s+-h$",
                        r"^free\s+-m$",
                        r"^echo\s+.*$"
                    ]
                    
                    is_allowed = False
                    for pattern in ALLOWLIST:
                        if re.match(pattern, cmd.strip()):
                            is_allowed = True
                            break
                            
                    if not is_allowed:
                        response = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"Error: Command '{cmd}' is not on the allowlist and was blocked."
                                    }
                                ],
                                "isError": True,
                                "returncode": -1
                            }
                        }
                        sys.stdout.write(json.dumps(response) + "\n")
                        sys.stdout.flush()
                        continue
                        
                    try:
                        res = subprocess.run(
                            cmd,
                            shell=True,
                            text=True,
                            capture_output=True,
                            timeout=10
                        )
                        output = res.stdout
                        if res.stderr:
                            output = f"{output}\n{res.stderr}" if output else res.stderr
                        
                        response = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": output.strip() if output else "Command executed successfully with no output"
                                    }
                                ],
                                "isError": res.returncode != 0,
                                "returncode": res.returncode
                            }
                        }
                    except subprocess.TimeoutExpired:
                        response = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "content": [{"type": "text", "text": "Command timed out after 10 seconds"}],
                                "isError": True,
                                "returncode": -2
                            }
                        }
                    except Exception as e:
                        response = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "content": [{"type": "text", "text": f"Subprocess exception: {str(e)}"}],
                                "isError": True,
                                "returncode": -1
                            }
                        }
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
                    
            elif method == "notifications/initialized":
                pass
                
        except Exception as e:
            log(f"Error handling request: {str(e)}")

if __name__ == "__main__":
    main()
