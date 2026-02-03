from __future__ import annotations

from typing import Any, Dict

from nucleus.registry.tool_registry import ToolRegistry
from tools.app.open import run as app_open
from tools.app.quit import run as app_quit
from tools.fs.list import run as fs_list
from tools.fs.mkdir import run as fs_mkdir
from tools.fs.move import run as fs_move
from tools.fs.stat import run as fs_stat
from tools.notify.send import run as notify_send


def build_tool_registry() -> ToolRegistry:
    """
    Register built-in deterministic tools shipped with the framework.
    """
    reg = ToolRegistry()

    def reg_tool(tool_id: str, title: str, side_effects: str, supports_dry_run: bool, args_schema: Dict[str, Any], impl):
        reg.register(
            {
                "tool_id": tool_id,
                "version": "0.1.0",
                "title": title,
                "description": "",
                "side_effects": side_effects,
                "destructive": False,
                "requires_explicit_allow": False,
                "supports_dry_run": supports_dry_run,
                "args_schema": args_schema,
            },
            impl,
        )

    reg_tool(
        "fs.list",
        "List directory entries",
        "filesystem",
        True,
        {"type": "object", "additionalProperties": False, "properties": {"path": {"type": "string"}}, "required": ["path"]},
        fs_list,
    )
    reg_tool(
        "fs.stat",
        "Stat a path",
        "filesystem",
        True,
        {"type": "object", "additionalProperties": False, "properties": {"path": {"type": "string"}}, "required": ["path"]},
        fs_stat,
    )
    reg_tool(
        "fs.mkdir",
        "Create a directory",
        "filesystem",
        True,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "path": {"type": "string"},
                "parents": {"type": "boolean"},
                "exist_ok": {"type": "boolean"},
            },
            "required": ["path"],
        },
        fs_mkdir,
    )
    reg_tool(
        "fs.move",
        "Move/rename a path",
        "filesystem",
        True,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"from": {"type": "string"}, "to": {"type": "string"}, "overwrite": {"type": "boolean"}},
            "required": ["from", "to"],
        },
        fs_move,
    )
    reg_tool(
        "notify.send",
        "Send a notification",
        "notification",
        True,
        {"type": "object", "additionalProperties": False, "properties": {"message": {"type": "string"}}, "required": ["message"]},
        notify_send,
    )
    reg_tool(
        "app.open",
        "Open app/file (contract only)",
        "app",
        True,
        {"type": "object", "additionalProperties": False, "properties": {"target": {"type": "string"}}, "required": ["target"]},
        app_open,
    )
    reg_tool(
        "app.quit",
        "Quit app (contract only)",
        "app",
        True,
        {"type": "object", "additionalProperties": False, "properties": {"app_id": {"type": "string"}}, "required": ["app_id"]},
        app_quit,
    )

    return reg

