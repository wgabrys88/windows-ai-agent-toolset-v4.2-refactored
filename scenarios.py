from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, Dict, Tuple

import winapi

# ============================================================================
# TOOLS SCHEMA - Tool Descriptions for LLM
# ============================================================================

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Capture screen and return current view with cursor visible.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move mouse using normalized coordinates 0..1000 relative to the screenshot.",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_mouse",
            "description": "Left click at current cursor position.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into the focused control.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_down",
            "description": "Scroll down by one notch.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# ============================================================================
# TOOL UTILITIES - Helper Functions
# ============================================================================

def _ok_payload(extra: Dict[str, Any] | None = None) -> str:
    """Generate success response payload."""
    d: Dict[str, Any] = {"ok": True}
    if extra:
        d.update(extra)
    return json.dumps(d, ensure_ascii=True, separators=(",", ":"))


def _err_payload(error_type: str, message: str) -> str:
    """Generate error response payload."""
    return json.dumps(
        {"ok": False, "error": {"type": error_type, "message": message}},
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _parse_args(arg_str: Any) -> Tuple[Dict[str, Any] | None, str | None]:
    """Parse JSON arguments string into dictionary."""
    if arg_str is None:
        arg_str = "{}"
    if not isinstance(arg_str, str):
        return None, _err_payload("invalid_arguments", "arguments must be a JSON string")
    try:
        val = json.loads(arg_str) if arg_str else {}
    except json.JSONDecodeError as e:
        return None, _err_payload("invalid_arguments", f"JSON decode error: {e.msg}")
    if not isinstance(val, dict):
        return None, _err_payload("invalid_arguments", "arguments must decode to an object")
    return val, None


def _parse_xy(arg_str: Any) -> Tuple[float | None, float | None, str | None]:
    """Parse and validate x,y coordinates from arguments."""
    args, err = _parse_args(arg_str)
    if err is not None:
        return None, None, err
    if "x" not in args or "y" not in args:
        return None, None, _err_payload("invalid_arguments", "missing x or y")
    try:
        x = float(args["x"])
        y = float(args["y"])
    except (TypeError, ValueError):
        return None, None, _err_payload("invalid_arguments", "x and y must be numbers")
    # Clamp to valid range
    if x < 0.0:
        x = 0.0
    elif x > 1000.0:
        x = 1000.0
    if y < 0.0:
        y = 0.0
    elif y > 1000.0:
        y = 1000.0
    return x, y, None


def _parse_text(arg_str: Any) -> Tuple[str | None, str | None]:
    """Parse text argument and sanitize to ASCII."""
    args, err = _parse_args(arg_str)
    if err is not None:
        return None, err
    if "text" not in args:
        return "", None
    t = "" if args["text"] is None else str(args["text"])
    t = t.encode("ascii", "ignore").decode("ascii")
    return t, None


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

def execute_tool(
    tool_name: str,
    arg_str: Any,
    call_id: str,
    dump_cfg: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
    """
    Execute a tool and return (tool_message, optional_user_message).
    
    Args:
        tool_name: Name of the tool to execute
        arg_str: JSON string of tool arguments
        call_id: Tool call ID for response
        dump_cfg: Configuration dict with keys: dump_dir, dump_prefix, dump_idx, target_w, target_h
    
    Returns:
        Tuple of (tool_response_message, optional_user_message_with_image)
    """
    
    # --- TAKE SCREENSHOT ---
    if tool_name == "take_screenshot":
        png_bytes, screen_w, screen_h = winapi.capture_screenshot_png(
            dump_cfg["target_w"], 
            dump_cfg["target_h"]
        )
        
        fn = os.path.join(
            dump_cfg["dump_dir"], 
            f"{dump_cfg['dump_prefix']}{dump_cfg['dump_idx']:04d}.png"
        )
        with open(fn, "wb") as f:
            f.write(png_bytes)
        
        dump_cfg["dump_idx"] += 1  # Increment for next screenshot
        
        b64 = base64.b64encode(png_bytes).decode("ascii")
        
        tool_msg = {
            "role": "tool",
            "tool_call_id": call_id,
            "name": tool_name,
            "content": _ok_payload({"file": fn, "screen_w": screen_w, "screen_h": screen_h}),
        }
        
        user_msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": "captured image data"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
            ],
        }
        
        return tool_msg, user_msg
    
    # --- MOVE MOUSE ---
    elif tool_name == "move_mouse":
        x, y, err = _parse_xy(arg_str)
        if err is not None:
            return {
                "role": "tool", 
                "tool_call_id": call_id, 
                "name": tool_name, 
                "content": err
            }, None
        
        winapi.move_mouse_norm(x, y)
        time.sleep(0.06)
        
        return {
            "role": "tool", 
            "tool_call_id": call_id, 
            "name": tool_name, 
            "content": _ok_payload()
        }, None
    
    # --- CLICK MOUSE ---
    elif tool_name == "click_mouse":
        _, err = _parse_args(arg_str)
        if err is not None:
            return {
                "role": "tool", 
                "tool_call_id": call_id, 
                "name": tool_name, 
                "content": err
            }, None
        
        winapi.click_mouse()
        time.sleep(0.06)
        
        return {
            "role": "tool", 
            "tool_call_id": call_id, 
            "name": tool_name, 
            "content": _ok_payload()
        }, None
    
    # --- TYPE TEXT ---
    elif tool_name == "type_text":
        text, err = _parse_text(arg_str)
        if err is not None:
            return {
                "role": "tool", 
                "tool_call_id": call_id, 
                "name": tool_name, 
                "content": err
            }, None
        
        winapi.type_text(text or "")
        time.sleep(0.06)
        
        return {
            "role": "tool", 
            "tool_call_id": call_id, 
            "name": tool_name, 
            "content": _ok_payload()
        }, None
    
    # --- SCROLL DOWN ---
    elif tool_name == "scroll_down":
        _, err = _parse_args(arg_str)
        if err is not None:
            return {
                "role": "tool", 
                "tool_call_id": call_id, 
                "name": tool_name, 
                "content": err
            }, None
        
        winapi.scroll_down()
        time.sleep(0.06)
        
        return {
            "role": "tool", 
            "tool_call_id": call_id, 
            "name": tool_name, 
            "content": _ok_payload()
        }, None
    
    # --- UNKNOWN TOOL ---
    else:
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": tool_name,
            "content": _err_payload("unknown_tool", tool_name),
        }, None


# ============================================================================
# SYSTEM PROMPT & SCENARIOS
# ============================================================================

SYSTEM_PROMPT = """You are an AI controlling a Windows 11 laptop. You interact with the computer exclusively through tool calls. Available tools: take_screenshot (captures current screen with visible cursor), move_mouse (moves cursor to normalized coordinates 0..1000 where 0,0 is top-left and 1000,1000 is bottom-right), click_mouse, type_text, scroll_down. Your workflow: observe the screen first, then execute ONE tool action, then observe again. Always verify cursor visibility in screenshots. You may answer in plain text only when done, stop calling tools only after you complete your task in full."""

SCENARIOS = [
    {
        "name": "Basic cursor observation",
        "task_prompt": "Look at the screen and report the current cursor position and shape."
    },
    {
        "name": "Center screen cursor movement",
        "task_prompt": "Look at the screen, then move the mouse cursor to the center of the screen."
    },
    {
        "name": "Click at current position",
        "task_prompt": "Look at the screen, then perform a click at the current cursor position, then verify the click result."
    },
    {
        "name": "Text typing test",
        "task_prompt": "Look at the screen, click into any focused text input if needed, then type \"hello\"."
    }
]
