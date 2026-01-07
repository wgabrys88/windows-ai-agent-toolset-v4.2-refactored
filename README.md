
# Windows 11 AI Agent - Technical Architecture Documentation

## 🎯 System Overview

This is a **vision-enabled AI agent** that controls a Windows 11 laptop through tool calls. The agent uses an LLM (via LM Studio) to observe the screen via screenshots and execute actions (mouse, keyboard) to complete user-defined tasks.

**Core Principle:** The AI observes → reasons → acts → observes again in a loop until the task is complete.

---

## 📊 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                 │
│  - Entry point & CLI argument handling                          │
│  - Configuration management (env vars)                          │
│  - LM Studio log extraction & cleanup                           │
│  - Signal handling (CTRL+C graceful shutdown)                   │
└────────────┬────────────────────────────────────────────────────┘
             │ imports & calls
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                         agent.py                                │
│  - Core agent loop (run_agent function)                         │
│  - LLM API communication (_post_json)                           │
│  - Message history management                                   │
│  - Screenshot pruning (memory optimization)                     │
│  - Tool call orchestration                                      │
└────────────┬────────────────────────────────────────────────────┘
             │ imports & delegates tool execution to
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      scenarios.py                               │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ TOOLS_SCHEMA (List[Dict])                                 │ │
│  │ - OpenAI function calling format                          │ │
│  │ - Tool names, descriptions, parameters                    │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Tool Helper Functions                                     │ │
│  │ - _ok_payload(): Success response generator               │ │
│  │ - _err_payload(): Error response generator                │ │
│  │ - _parse_args(): JSON argument parser                     │ │
│  │ - _parse_xy(): Coordinate validator (0-1000 range)        │ │
│  │ - _parse_text(): Text sanitizer (ASCII only)              │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ execute_tool(name, args, call_id, dump_cfg)              │ │
│  │ - Dispatcher for all tool implementations                │ │
│  │ - Returns (tool_message, optional_user_message)          │ │
│  │                                                           │ │
│  │ Tool Implementations:                                     │ │
│  │  • take_screenshot: Capture + save + base64 encode       │ │
│  │  • move_mouse: Validate coords + move cursor             │ │
│  │  • click_mouse: Left click at current position           │ │
│  │  • type_text: Type ASCII text via keyboard               │ │
│  │  • scroll_down: Scroll down one notch                    │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ SYSTEM_PROMPT (str)                                       │ │
│  │ - Agent behavior instructions for LLM                     │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ SCENARIOS (List[Dict])                                    │ │
│  │ - Pre-defined test scenarios with task prompts           │ │
│  └───────────────────────────────────────────────────────────┘ │
└────────────┬────────────────────────────────────────────────────┘
             │ imports & calls OS-level functions from
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                        winapi.py                                │
│  - Low-level Windows API wrappers (ctypes)                      │
│  - NO BUSINESS LOGIC - pure OS interface layer                  │
│                                                                 │
│  Functions:                                                     │
│  • init_dpi(): Set DPI awareness context                        │
│  • get_screen_size(): Query screen dimensions                   │
│  • norm_to_screen_px(): Convert 0-1000 → pixel coords           │
│  • capture_screenshot_png(): GDI+ screenshot with cursor        │
│  • move_mouse_norm(): Move mouse (normalized coords)            │
│  • click_mouse(): Send left click input                         │
│  • scroll_down(): Send scroll wheel input                       │
│  • type_text(): Send Unicode keyboard inputs                    │
│                                                                 │
│  Windows APIs used:                                             │
│  - user32.dll (mouse, keyboard, cursor, DPI)                    │
│  - gdi32.dll (screenshot, bitmap operations)                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📂 File-by-File Breakdown

### 🔷 **main.py** - Application Entry Point

**Purpose:** CLI interface, configuration, and log management

**Responsibilities:**
- Parse command-line arguments (`scenario_num`)
- Load environment variables for configuration
- Initialize DPI awareness via `winapi.init_dpi()`
- Select scenario from `scenarios.SCENARIOS`
- Create dump directory for screenshots
- Call `agent.run_agent()` with configuration
- Handle CTRL+C gracefully (signal handlers)
- Extract and clean LM Studio logs after execution

**Key Functions:**
| Function | Purpose |
|----------|---------|
| `main()` | Entry point, orchestrates entire flow |
| `_get_env_str/int/float()` | Environment variable loaders with defaults |
| `_handle_cleanup()` | Export logs on exit (normal or interrupted) |
| `_signal_handler()` | SIGINT/SIGTERM handler for graceful shutdown |
| `_export_and_clean_current_run()` | Extract relevant logs from LM Studio |
| `_clean_log_file()` | Format logs, truncate base64 images |

**Configuration Parameters:**
```python
cfg = {
    "endpoint": str,              # LM Studio API endpoint
    "model_id": str,              # Model identifier
    "timeout": int,               # Request timeout (seconds)
    "temperature": float,         # LLM temperature
    "max_tokens": int,            # Max response tokens
    "target_w": int,              # Screenshot width (pixels)
    "target_h": int,              # Screenshot height (pixels)
    "dump_dir": str,              # Screenshot save directory
    "dump_prefix": str,           # Screenshot filename prefix
    "dump_start": int,            # Starting screenshot number
    "keep_last_screenshots": int, # How many screenshots to keep in context
    "max_steps": int,             # Maximum agent loop iterations
    "step_delay": float,          # Delay between steps (seconds)
}
```

**Dependencies:**
- `scenarios.py` → Access `SYSTEM_PROMPT`, `SCENARIOS`, `TOOLS_SCHEMA`
- `agent.py` → Call `run_agent()`
- `winapi.py` → Call `init_dpi()`

**Execution Flow:**
```
1. Parse CLI args → Get scenario number
2. Load configuration from environment variables
3. Initialize DPI awareness
4. Get system prompt and task prompt from scenarios.py
5. Create screenshot dump directory
6. Record start timestamp
7. Call run_agent() with configuration
8. Record end timestamp
9. Export and clean LM Studio logs
10. Print final agent response
```

---

### 🔷 **agent.py** - LLM Agent Loop Orchestration

**Purpose:** Manage conversation with LLM and coordinate tool execution

**Responsibilities:**
- Send messages to LLM API endpoint
- Receive and parse LLM responses
- Detect tool calls in responses
- Delegate tool execution to `scenarios.execute_tool()`
- Manage conversation history
- Prune old screenshots from context (memory optimization)
- Handle multiple tool call errors (only 1 allowed per response)
- Control agent loop termination

**Key Functions:**
| Function | Purpose |
|----------|---------|
| `run_agent()` | Main agent loop, returns final response string |
| `_post_json()` | HTTP POST to LLM API with JSON payload |
| `_prune_old_screenshots()` | Remove old screenshot data from messages, keep only references |

**Agent Loop Logic:**
```python
for step in range(max_steps):
    1. Send messages to LLM API
    2. Get response (may contain tool_calls)
    3. If no tool_calls → return final response (DONE)
    4. If multiple tool_calls → error (only 1 allowed)
    5. Extract tool call: name, arguments, call_id
    6. Call scenarios.execute_tool(name, args, call_id, dump_cfg)
    7. Append tool response to messages
    8. If tool returned user_message (screenshot):
       - Append image to messages
       - Prune old screenshots
    9. Sleep for step_delay
    10. Continue loop
```

**Message Format:**
```python
messages = [
    {"role": "system", "content": str},
    {"role": "user", "content": str},
    {"role": "assistant", "content": str, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": str, "name": str, "content": str},
    {"role": "user", "content": [
        {"type": "text", "text": str},
        {"type": "image_url", "image_url": {"url": str}}
    ]},
]
```

**Dependencies:**
- `scenarios.py` → Call `execute_tool()`, access `_err_payload()`
- LM Studio API → Send/receive chat completions

**Does NOT:**
- ❌ Know about specific tools (delegated to scenarios.py)
- ❌ Parse tool arguments (delegated to scenarios.py)
- ❌ Call Windows APIs directly (delegated via scenarios.py → winapi.py)

---

### 🔷 **scenarios.py** - Tool Definitions & Implementations

**Purpose:** Single source of truth for all tools, scenarios, and system prompt

**Responsibilities:**
- Define tool schemas for LLM (OpenAI function calling format)
- Implement all tool execution logic
- Parse and validate tool arguments
- Generate success/error response payloads
- Store system prompt and task scenarios

**Architecture:**
```
┌─────────────────────────────────────────────────┐
│ TOOLS_SCHEMA                                    │
│ - OpenAI-compatible tool definitions            │
│ - Sent to LLM so it knows what tools exist      │
└─────────────────────────────────────────────────┘
          ↓ references
┌─────────────────────────────────────────────────┐
│ Helper Functions                                │
│ - _ok_payload(), _err_payload()                 │
│ - _parse_args(), _parse_xy(), _parse_text()     │
└─────────────────────────────────────────────────┘
          ↓ used by
┌─────────────────────────────────────────────────┐
│ execute_tool(name, args, call_id, dump_cfg)    │
│ - Main dispatcher                               │
│ - Calls winapi.py functions                     │
│ - Returns (tool_msg, user_msg | None)           │
└─────────────────────────────────────────────────┘
          ↓ supports
┌─────────────────────────────────────────────────┐
│ SYSTEM_PROMPT & SCENARIOS                       │
│ - Agent behavior definition                     │
│ - Test scenarios                                │
└─────────────────────────────────────────────────┘
```

**TOOLS_SCHEMA Structure:**
```python
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": str,              # Tool identifier
            "description": str,       # What the tool does (for LLM)
            "parameters": {           # JSON Schema for arguments
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
    },
    # ... more tools
]
```

**Available Tools:**

| Tool Name | Arguments | Description | Returns |
|-----------|-----------|-------------|---------|
| `take_screenshot` | None | Captures screen with cursor, saves PNG, encodes base64 | (tool_msg, user_msg_with_image) |
| `move_mouse` | `x: float, y: float` | Moves cursor to normalized coords (0-1000) | (tool_msg, None) |
| `click_mouse` | None | Left-clicks at current cursor position | (tool_msg, None) |
| `type_text` | `text: str` | Types ASCII text via keyboard | (tool_msg, None) |
| `scroll_down` | None | Scrolls down one wheel notch | (tool_msg, None) |

**execute_tool() Return Format:**
```python
# Success case
tool_msg = {
    "role": "tool",
    "tool_call_id": str,
    "name": str,
    "content": '{"ok": true, ...}'  # JSON string
}

# For screenshot tool, also returns:
user_msg = {
    "role": "user",
    "content": [
        {"type": "text", "text": "captured image data"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    ]
}

# Error case
tool_msg = {
    "role": "tool",
    "tool_call_id": str,
    "name": str,
    "content": '{"ok": false, "error": {"type": str, "message": str}}'
}
```

**dump_cfg Parameter:**
```python
dump_cfg = {
    "dump_dir": str,      # Where to save screenshots
    "dump_prefix": str,   # Filename prefix
    "dump_idx": int,      # Current screenshot number (mutable!)
    "target_w": int,      # Screenshot target width
    "target_h": int,      # Screenshot target height
}
```

**Dependencies:**
- `winapi.py` → All OS-level operations
- No dependencies on `agent.py` or `main.py`

**Adding a New Tool (Step-by-Step for AI):**

1. **Add to TOOLS_SCHEMA:**
```python
{
    "type": "function",
    "function": {
        "name": "new_tool_name",
        "description": "What it does (clear explanation for LLM)",
        "parameters": {
            "type": "object",
            "properties": {
                "arg1": {"type": "string"},
                "arg2": {"type": "number"}
            },
            "required": ["arg1"]
        }
    }
}
```

2. **Add to execute_tool() function:**
```python
elif tool_name == "new_tool_name":
    # Parse arguments
    args, err = _parse_args(arg_str)
    if err is not None:
        return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None
    
    # Validate specific arguments
    arg1 = args.get("arg1")
    if not arg1:
        return {"role": "tool", "tool_call_id": call_id, "name": tool_name, 
                "content": _err_payload("missing_arg", "arg1 required")}, None
    
    # Execute action (call winapi function or other logic)
    result = winapi.some_new_function(arg1)
    
    # Return success
    return {"role": "tool", "tool_call_id": call_id, "name": tool_name, 
            "content": _ok_payload({"result": result})}, None
```

3. **No other files need modification!**

---

### 🔷 **winapi.py** - Windows API Abstraction Layer

**Purpose:** Provide clean Python interface to Windows APIs (ctypes)

**Responsibilities:**
- Wrap user32.dll and gdi32.dll functions
- Handle ctypes structure definitions
- Manage DPI awareness
- Perform low-level screenshot capture (GDI+)
- Send low-level mouse/keyboard input events
- Convert coordinate systems

**Key Characteristics:**
- ✅ **Pure technical layer** - no business logic
- ✅ **Reusable** - functions can be used outside agent context
- ✅ **Stateless** - no internal state management
- ✅ **Generic** - not coupled to LLM or tool concepts

**Function Reference:**

| Function | Parameters | Returns | Purpose |
|----------|-----------|---------|---------|
| `init_dpi()` | None | None | Set process to per-monitor DPI aware v2 |
| `get_screen_size()` | None | `(width, height)` | Get primary monitor dimensions |
| `norm_to_screen_px(xn, yn, screen_w, screen_h)` | `xn: float, yn: float, screen_w: int, screen_h: int` | `(x_px, y_px)` | Convert 0-1000 coords to pixels |
| `capture_screenshot_png(target_w, target_h)` | `target_w: int, target_h: int` | `(png_bytes, screen_w, screen_h)` | Capture screen, resize, encode PNG |
| `move_mouse_norm(xn, yn)` | `xn: float, yn: float` | `(screen_w, screen_h)` | Move cursor to normalized position |
| `click_mouse()` | None | None | Send left button down + up |
| `scroll_down()` | None | None | Send wheel scroll down (-120 delta) |
| `type_text(text)` | `text: str` | None | Send Unicode keyboard events |

**Screenshot Implementation Details:**
```
1. Get screen dimensions via GetSystemMetrics
2. Get desktop device context (DC)
3. Create compatible memory DC
4. Create DIB section with target dimensions
5. StretchBlt from screen DC to memory DC (resize)
6. Get cursor info and icon info
7. Draw cursor icon onto memory DC at scaled position
8. Read BGRA pixel data from DIB section
9. Convert BGRA → RGB (discard alpha)
10. Encode as PNG (zlib compression)
11. Return PNG bytes + original screen dimensions
```

**Coordinate System:**
- **Input to move_mouse_norm:** 0-1000 normalized coords (LLM outputs this)
- **Screen coords:** Actual pixel coordinates (e.g., 1920x1080)
- **Conversion:** `pixel_x = (norm_x / 1000.0) * (screen_width - 1)`

**Windows API Structures Used:**
- `POINT` - Screen coordinates
- `CURSORINFO` - Cursor position and visibility
- `ICONINFO` - Cursor icon data
- `BITMAPINFOHEADER` - Bitmap format
- `MOUSEINPUT`, `KEYBDINPUT` - Input events
- `INPUT` - Generic input union

**Dependencies:**
- `ctypes` - Python's FFI library
- `user32.dll` - Windows user interface API
- `gdi32.dll` - Windows graphics device interface
- No dependencies on other project files

**Constants Reference:**
```python
# DPI
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

# Coordinate constants
0-1000 normalized → 0-screen_dimension pixels

# Mouse events
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800

# Keyboard events
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
```

---

## 🔄 Data Flow Examples

### Example 1: Screenshot Tool Execution

```
1. LLM → agent.py
   Response: {"tool_calls": [{"function": {"name": "take_screenshot", "arguments": "{}"}}]}

2. agent.py → scenarios.py
   Call: execute_tool("take_screenshot", "{}", "call_abc123", dump_cfg)

3. scenarios.py → winapi.py
   Call: capture_screenshot_png(1344, 756)

4. winapi.py → Windows (user32.dll, gdi32.dll)
   - GetDC(NULL) → Get screen DC
   - CreateCompatibleDC → Create memory DC
   - StretchBlt → Copy and resize
   - GetCursorInfo → Get cursor position
   - DrawIconEx → Draw cursor on bitmap

5. winapi.py → scenarios.py
   Return: (png_bytes, 1920, 1080)

6. scenarios.py
   - Save PNG to dumps/screen_0001.png
   - Base64 encode PNG
   - Build tool_msg with file path and dimensions
   - Build user_msg with base64 image

7. scenarios.py → agent.py
   Return: (tool_msg, user_msg)

8. agent.py
   - Append tool_msg to messages
   - Append user_msg with image to messages
   - Prune old screenshots

9. agent.py → LLM
   Send updated messages with new screenshot
```

### Example 2: Move Mouse Tool Execution

```
1. LLM → agent.py
   Response: {"tool_calls": [{"function": {"name": "move_mouse", "arguments": '{"x": 500, "y": 500}'}}]}

2. agent.py → scenarios.py
   Call: execute_tool("move_mouse", '{"x": 500, "y": 500}', "call_def456", dump_cfg)

3. scenarios.py
   - Call _parse_xy('{"x": 500, "y": 500}')
   - Extract x=500.0, y=500.0
   - Clamp to 0-1000 range (already valid)

4. scenarios.py → winapi.py
   Call: move_mouse_norm(500.0, 500.0)

5. winapi.py
   - Get screen size: (1920, 1080)
   - Convert: pixel_x = (500/1000) * 1919 = 959
   - Convert: pixel_y = (500/1000) * 1079 = 539

6. winapi.py → Windows (user32.dll)
   Call: SetCursorPos(959, 539)

7. winapi.py → scenarios.py
   Return: (1920, 1080)

8. scenarios.py
   - Sleep 0.06 seconds
   - Build tool_msg with success payload

9. scenarios.py → agent.py
   Return: (tool_msg, None)

10. agent.py
    - Append tool_msg to messages
    - No user_msg, so no pruning

11. agent.py → LLM
    Send updated messages
```

---

## 🧪 Testing & Debugging

### Running a Scenario

```bash
python main.py 1  # Run scenario 1 (cursor observation)
python main.py 2  # Run scenario 2 (center cursor)
python main.py 3  # Run scenario 3 (click)
python main.py 4  # Run scenario 4 (type text)
```

### Environment Variables

```bash
# LM Studio Configuration
LMSTUDIO_ENDPOINT=http://localhost:1234/v1/chat/completions
LMSTUDIO_MODEL=your-model-name
LMSTUDIO_TIMEOUT=240
LMSTUDIO_TEMPERATURE=0.2
LMSTUDIO_MAX_TOKENS=2048

# Agent Configuration
AGENT_IMAGE_W=1344
AGENT_IMAGE_H=756
AGENT_DUMP_DIR=dumps
AGENT_DUMP_PREFIX=screen_
AGENT_DUMP_START=1
AGENT_KEEP_LAST_SCREENSHOTS=2
AGENT_MAX_STEPS=10
AGENT_STEP_DELAY=0.4
```

### Log Files Generated

After execution, main.py generates:
1. `python_main_py_<scenario>_lmstudio_raw.log` - Raw LM Studio logs (filtered by timestamp)
2. `python_main_py_<scenario>_lmstudio_raw_clean.log` - Formatted logs with truncated base64

### Screenshot Files

Saved to `dumps/` directory:
- `screen_0001.png` - First screenshot
- `screen_0002.png` - Second screenshot
- etc.

---

## 🤖 AI Developer Guidelines

### When Modifying the System

**To add a new tool:**
1. Edit `scenarios.py` only
2. Add entry to `TOOLS_SCHEMA`
3. Add case to `execute_tool()` function
4. If new OS capability needed, add function to `winapi.py` first

**To modify agent behavior:**
1. Edit `scenarios.SYSTEM_PROMPT`
2. Optionally adjust `agent.py` loop logic

**To add a new scenario:**
1. Edit `scenarios.SCENARIOS` list
2. Add dict with `name` and `task_prompt`

**To change LLM parameters:**
1. Modify environment variables or defaults in `main.py`

### Dependency Rules (CRITICAL)

```
main.py ──CAN IMPORT──> agent.py, scenarios.py, winapi.py
agent.py ──CAN IMPORT──> scenarios.py
scenarios.py ──CAN IMPORT──> winapi.py

❌ FORBIDDEN:
- agent.py importing main.py
- scenarios.py importing agent.py or main.py
- winapi.py importing ANY project file
```

### Module Responsibilities (MUST NOT VIOLATE)

| Module | CAN DO | CANNOT DO |
|--------|--------|-----------|
| **main.py** | CLI, config, logging, signal handling | Tool implementation, LLM communication, Windows API calls |
| **agent.py** | LLM loop, message management, tool call detection | Tool implementation, Windows API calls, log management |
| **scenarios.py** | Tool definitions, argument parsing, tool dispatch | LLM communication, configuration, log management |
| **winapi.py** | Windows API wrappers, coordinate conversion | Tool schemas, LLM concepts, business logic |

### Error Handling Strategy

**Validation errors** (bad arguments) → Return error payload via `_err_payload()`
```python
{"ok": false, "error": {"type": "invalid_arguments", "message": "..."}}
```

**System errors** (Windows API failure) → Raise exception, let main.py handle

**LLM errors** (timeout, network) → Raise exception, let main.py handle

---

## 📋 System Requirements

- **OS:** Windows 11 (uses Windows-specific APIs)
- **Python:** 3.10+ (uses `|` union syntax)
- **External Process:** LM Studio running locally (default: localhost:1234)
- **Model Requirements:** Vision-capable LLM (e.g., Llama 3.2 Vision, Qwen2-VL)

---

## 🔐 Security Considerations

- **Full system control:** This agent can control mouse and keyboard
- **Screenshot access:** Captures all screen content
- **No sandboxing:** Runs with user's permissions
- **LLM prompt injection:** System prompt must be carefully designed to prevent malicious instructions

---

## 📖 Code Quality Standards

- **Type hints:** All functions have complete type annotations
- **Docstrings:** All public functions documented
- **Error messages:** Clear, actionable error descriptions
- **No magic numbers:** All constants are named
- **Separation of concerns:** Each module has single responsibility
- **Testability:** Functions are small, pure where possible

---

## 🔮 Future Enhancement Ideas

1. **Right-click support** - Add `click_mouse_right()` tool
2. **Drag and drop** - Add `drag_mouse(x1, y1, x2, y2)` tool
3. **Keyboard shortcuts** - Add `press_key(key_name)` tool (Ctrl+C, etc.)
4. **Window management** - Add `get_window_list()`, `focus_window()` tools
5. **OCR integration** - Add text extraction from screenshots
6. **Multi-monitor support** - Specify target monitor in screenshot tool
7. **Recording mode** - Save all actions as replay script
8. **Web API mode** - Expose agent via REST API

---

## 📚 Additional Resources

- **OpenAI Function Calling Docs:** https://platform.openai.com/docs/guides/function-calling
- **Windows API Reference:** https://learn.microsoft.com/en-us/windows/win32/api/
- **ctypes Documentation:** https://docs.python.org/3/library/ctypes.html

---

## 📝 Version History

- **v4.2** - Refactored (current)

---

**Last Updated:** 2026-01-7
**Maintainer:** wgabrys88
```

---

This README is designed to be **both human and AI-readable**. An AI system reading this file will understand:

1. ✅ **What each file does** (responsibilities clearly listed)
2. ✅ **How files interact** (dependency diagrams + data flow examples)
3. ✅ **Where to make changes** (explicit guidelines for each modification type)
4. ✅ **What rules must be followed** (dependency rules, module boundaries)
5. ✅ **How to add new features** (step-by-step tool addition guide)
6. ✅ **Complete function signatures** (parameters, returns, types)

The AI can use this as a **complete mental model** of the system to make modifications without breaking the architecture.
