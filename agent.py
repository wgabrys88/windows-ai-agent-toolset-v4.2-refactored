from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, List

import scenarios


def _post_json(payload: Dict[str, Any], endpoint: str, timeout: int) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _prune_old_screenshots(messages: List[Dict[str, Any]], keep_last: int) -> List[Dict[str, Any]]:
    idxs = []
    for i, m in enumerate(messages):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if not isinstance(c, list):
            continue
        if any(isinstance(p, dict) and p.get("type") == "image_url" for p in c):
            idxs.append(i)

    if len(idxs) <= keep_last:
        return messages

    for i in idxs[:-keep_last]:
        file_hint = ""
        if i > 0 and messages[i - 1].get("role") == "tool":
            try:
                meta = json.loads(messages[i - 1].get("content", "{}"))
                if isinstance(meta, dict) and meta.get("ok") and meta.get("file"):
                    file_hint = f" (omitted; file={meta['file']})"
            except Exception:
                pass
        messages[i]["content"] = f"captured image data{file_hint}"

    return messages


def run_agent(
    system_prompt: str,
    task_prompt: str,
    tools_schema: List[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> str:
    endpoint = cfg["endpoint"]
    model_id = cfg["model_id"]
    timeout = cfg["timeout"]
    temperature = cfg["temperature"]
    max_tokens = cfg["max_tokens"]
    keep_last_screenshots = cfg["keep_last_screenshots"]
    max_steps = cfg["max_steps"]
    step_delay = cfg["step_delay"]

    # Prepare dump configuration for tool execution
    dump_cfg = {
        "dump_dir": cfg["dump_dir"],
        "dump_prefix": cfg["dump_prefix"],
        "dump_idx": cfg["dump_start"],
        "target_w": cfg["target_w"],
        "target_h": cfg["target_h"],
    }

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_prompt},
    ]

    last_content = ""

    for _ in range(max_steps):
        resp = _post_json(
            {
                "model": model_id,
                "messages": messages,
                "tools": tools_schema,
                "tool_choice": "auto",
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            endpoint,
            timeout,
        )

        msg = resp["choices"][0]["message"]
        messages.append(msg)

        if isinstance(msg.get("content"), str):
            last_content = msg["content"]

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return last_content

        if len(tool_calls) > 1:
            for extra_tc in tool_calls[1:]:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": extra_tc["id"],
                        "name": extra_tc["function"]["name"],
                        "content": scenarios._err_payload(
                            "too_many_tool_calls", "only one tool call per response allowed"
                        ),
                    }
                )
            tool_calls = tool_calls[:1]

        tc = tool_calls[0]
        name = tc["function"]["name"]
        arg_str = tc["function"].get("arguments")
        call_id = tc["id"]

        # Execute tool via scenarios module
        tool_msg, user_msg = scenarios.execute_tool(name, arg_str, call_id, dump_cfg)
        messages.append(tool_msg)
        
        if user_msg is not None:
            messages.append(user_msg)
            messages = _prune_old_screenshots(messages, keep_last_screenshots)

        time.sleep(step_delay)

    return last_content
