import re
import os
from typing import Any, Tuple, List, Dict

def _parse_block_format(lines: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """
    Parses block-based step formats.
    Looks for step blocks starting with '## Step', parses descriptions from 
    'Description:', and extracts commands inside code blocks.
    """
    steps = []
    commands = {}
    
    current_step = None
    collecting_command = False
    command_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Check if line matches a step header, e.g. "## Step 1", "## Step 1: Restart service", "## Step - Run query"
        step_header_match = re.match(r"^##+\s+Step\b\s*\d*(.*)$", stripped, re.IGNORECASE)
        if step_header_match:
            # Save the previous step before starting a new one
            if current_step:
                # Determine description/name
                step_name = current_step.get("description", "").strip()
                if not step_name:
                    step_name = current_step.get("fallback_desc", "").strip()
                if not step_name:
                    # Use heading text as fallback, clean up the # characters
                    step_name = re.sub(r"^#+\s*", "", current_step["heading"]).strip()
                
                if step_name:
                    steps.append(step_name)
                    if current_step.get("command"):
                        commands[step_name] = current_step["command"]
            
            # Start new step
            heading_desc = step_header_match.group(1).strip()
            # Clean leading colons, dashes, spaces
            heading_desc = re.sub(r"^[:\-–—\s]+", "", heading_desc).strip()
            heading_desc = re.sub(r"\*\*|`|\*", "", heading_desc).strip()
            
            current_step = {
                "heading": stripped,
                "description": heading_desc,
                "fallback_desc": "",
                "command": ""
            }
            collecting_command = False
            command_lines = []
            continue
            
        if current_step is not None:
            # Check for Description: ...
            desc_match = re.match(r"^Description:\s*(.+)$", stripped, re.IGNORECASE)
            if desc_match:
                step_desc = desc_match.group(1).strip()
                step_desc = re.sub(r"\*\*|`|\*", "", step_desc).strip().rstrip(":-").strip()
                current_step["description"] = step_desc
                continue
            
            # Support inline commands on a single line
            cmd_inline_match = re.match(r"^(?:Command|Executes):\s*`?([^`]+)`?$", stripped, re.IGNORECASE)
            if cmd_inline_match and not collecting_command:
                current_step["command"] = cmd_inline_match.group(1).strip()
                continue
                
            # Support code block command
            if stripped.startswith("```"):
                if collecting_command:
                    current_step["command"] = "\n".join(command_lines).strip()
                    collecting_command = False
                else:
                    collecting_command = True
                    command_lines = []
                continue
                
            if collecting_command:
                command_lines.append(line)
                continue
                
            # If we don't have a description yet, and the line is not empty, not a header, not expected output
            if not current_step["description"] and stripped:
                if not any(stripped.lower().startswith(x) for x in ["command:", "expected output:", "output:", "note:", "```"]):
                    current_step["fallback_desc"] = stripped
                    
    # Save the final step
    if current_step:
        step_name = current_step.get("description", "").strip()
        if not step_name:
            step_name = current_step.get("fallback_desc", "").strip()
        if not step_name:
            step_name = re.sub(r"^#+\s*", "", current_step["heading"]).strip()
        
        if step_name:
            steps.append(step_name)
            if current_step.get("command"):
                commands[step_name] = current_step["command"]
                
    return steps, commands

def _parse_list_format(lines: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """
    Parses list-based markdown runbook steps.
    Identifies if a steps section exists and collects list items under it.
    Falls back to document-wide list parsing if no step section header is found.
    """
    steps = []
    commands = {}
    
    # 1. Look for a steps section header
    steps_section_index = -1
    for i, line in enumerate(lines):
        # Match sub-headings like ## Steps, ## Execution, ## Checklist, etc.
        if re.match(r"^##+\s+.*(?:step|checklist|action|procedure|execution|tasks).*", line.strip(), re.IGNORECASE):
            steps_section_index = i
            break
            
    # If steps section header is found, extract lines under it until the next header
    target_lines = lines
    if steps_section_index != -1:
        target_lines = []
        for line in lines[steps_section_index + 1:]:
            if line.strip().startswith("#"):
                # Hit next section header, stop collecting
                break
            target_lines.append(line)
            
    # 2. Parse list items (numbered lists, bullets, checkboxes) and their following code blocks
    current_step = None
    collecting_command = False
    command_lines = []
    
    for line in target_lines:
        line_str = line.strip()
        
        # Check if this line is a new list item
        # Match standard bullet items (-/*/+), numbered items (1./1)), or checkbox tasks (- [ ]/- [x])
        list_match = re.match(r"^\s*(?:\d+[\.)]|[-*+])\s+(.+)$", line_str)
        if list_match:
            # If we were already collecting a step, save it
            if current_step:
                steps.append(current_step["name"])
                if current_step.get("command"):
                    commands[current_step["name"]] = current_step["command"]
                    
            full_text = list_match.group(1).strip()
            full_text = re.sub(r"^\[[ xX]\]\s*", "", full_text).strip()
            
            # Extract inline command in backticks
            cmd_match = re.search(r"`([^`]+)`", full_text)
            if cmd_match:
                command = cmd_match.group(1).strip()
                step = re.split(r"[:\-]?\s*`", full_text)[0].strip()
                step = re.sub(r"\*\*|`|\*", "", step).strip()
                current_step = {"name": step, "command": command}
            else:
                step = re.sub(r"\*\*|`|\*", "", full_text).strip()
                current_step = {"name": step, "command": ""}
                
            collecting_command = False
            command_lines = []
            continue
            
        if current_step is not None:
            # Check if there is a command block following the list item
            if line_str.startswith("```"):
                if collecting_command:
                    current_step["command"] = "\n".join(command_lines).strip()
                    collecting_command = False
                else:
                    collecting_command = True
                    command_lines = []
                continue
                
            if collecting_command:
                command_lines.append(line)
                continue
                
    # Save the final step
    if current_step:
        steps.append(current_step["name"])
        if current_step.get("command"):
            commands[current_step["name"]] = current_step["command"]
            
    return steps, commands

def _parse_heading_steps_format(lines: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """
    Parses documents where each subheading (## or ###) represents a step.
    Filters out common non-step headers like 'Objective', 'Expected Output', 'Title', 'Prerequisites'.
    """
    steps = []
    commands = {}
    
    current_step = None
    collecting_command = False
    command_lines = []
    
    non_step_patterns = [
        r"^objective", r"^expected\s+output", r"^prerequisites", r"^summary", r"^notes?", r"^overview", r"^introduction", r"^setup", r"^requirements"
    ]
    
    for line in lines:
        stripped = line.strip()
        
        # Match any heading starting with ## or ### (but not #)
        header_match = re.match(r"^(##+)\s+(.+)$", stripped)
        if header_match:
            heading_text = header_match.group(2).strip()
            # Check if this heading is a non-step section
            is_non_step = any(re.match(pat, heading_text, re.IGNORECASE) for pat in non_step_patterns)
            
            if not is_non_step:
                # Save previous step
                if current_step:
                    steps.append(current_step["name"])
                    if current_step.get("command"):
                        commands[current_step["name"]] = current_step["command"]
                        
                current_step = {"name": re.sub(r"\*\*|`|\*", "", heading_text).strip(), "command": ""}
                collecting_command = False
                command_lines = []
                continue
                
        if current_step is not None:
            # Check for inline Command: top or Command: `top`
            cmd_inline_match = re.match(r"^(?:Command|Executes):\s*`?([^`]+)`?$", stripped, re.IGNORECASE)
            if cmd_inline_match and not collecting_command:
                current_step["command"] = cmd_inline_match.group(1).strip()
                continue
                
            # Support code block command
            if stripped.startswith("```"):
                if collecting_command:
                    current_step["command"] = "\n".join(command_lines).strip()
                    collecting_command = False
                else:
                    collecting_command = True
                    command_lines = []
                continue
                
            if collecting_command:
                command_lines.append(line)
                continue
                
            # Or if it contains inline backticks command on any line
            if not current_step["command"] and not collecting_command:
                cmd_match = re.search(r"`([^`]+)`", stripped)
                if cmd_match:
                    candidate = cmd_match.group(1).strip()
                    current_step["command"] = candidate
                    
    # Save the final step
    if current_step:
        steps.append(current_step["name"])
        if current_step.get("command"):
            commands[current_step["name"]] = current_step["command"]
            
    return steps, commands

def parse_runbook(filepath_or_content: Any) -> dict:
    """
    Reads and parses a Markdown runbook to extract metadata, steps, and inline commands.
    
    Supports:
      1. Block-Based Format: '## Step X' headers containing 'Description:' and command code blocks.
      2. List-Based Format: Bulleted, numbered, or checkbox lists inside a Steps section or globally.
      3. Heading-Based Format: Subheadings (## or ###) that represent steps directly.
      
    Returns:
        dict: A dictionary containing:
            {
                "title": str,
                "objective": str,
                "steps": [str],
                "commands": {step_name: command_string}
            }
    """
    title = ""
    objective = ""

    # Read input safely
    content = ""
    if hasattr(filepath_or_content, "read"):
        try:
            if hasattr(filepath_or_content, "seek"):
                filepath_or_content.seek(0)
            raw_data = filepath_or_content.read()
            content = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)
        except Exception:
            content = ""
    else:
        # Prevent Windows syntax exception by checking newlines and path length
        is_path = False
        if isinstance(filepath_or_content, str) and "\n" not in filepath_or_content and len(filepath_or_content) < 260:
            try:
                is_path = os.path.exists(filepath_or_content)
            except Exception:
                is_path = False
                
        if is_path:
            try:
                with open(filepath_or_content, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = ""
        else:
            content = filepath_or_content if isinstance(filepath_or_content, str) else ""

    lines = content.splitlines()

    # Extract Title (starting with '#')
    for line in lines:
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            title = match.group(1).strip()
            title = re.sub(r"\*\*|`|\*", "", title).strip()
            break

    # Extract Objective (first non-empty line after ## Objective)
    for i, line in enumerate(lines):
        if re.match(r"^##\s*Objective", line.strip(), re.IGNORECASE):
            for sub in lines[i + 1:]:
                sub = sub.strip()
                if sub and not sub.startswith("#"):
                    objective = sub
                    objective = re.sub(r"\*\*|`|\*", "", objective).strip()
                    break
            break

    # Extract Steps + Commands
    # Try block-based format first
    steps, commands = _parse_block_format(lines)

    # Fallback to list-based parsing if no block steps were found
    if not steps:
        steps, commands = _parse_list_format(lines)

    # Fallback to heading-based parsing if still no steps were found
    if not steps:
        steps, commands = _parse_heading_steps_format(lines)

    # Return clean dictionary
    return {
        "title": title if title else "Runbook Instructions",
        "objective": objective if objective else "No objective specified.",
        "steps": steps,
        "commands": commands
    }