from __future__ import annotations

from typing import Any, Callable


ToolFunc = Callable[[dict[str, Any], bool], dict[str, Any]]


class ToolRegistry:
    """
    Registry for deterministic tools and their metadata.
    """

    def __init__(self) -> None:
        self._defs: dict[str, dict[str, Any]] = {}
        self._impls: dict[str, ToolFunc] = {}

    def register(self, tool_def: dict[str, Any], impl: ToolFunc) -> None:
        tool_id = tool_def["tool_id"]
        self._defs[tool_id] = tool_def
        self._impls[tool_id] = impl

    def get(self, tool_id: str) -> dict[str, Any] | None:
        return self._defs.get(tool_id)

    def call(self, tool_id: str, args: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
        impl = self._impls.get(tool_id)
        if impl is None:
            raise KeyError(tool_id)
        return impl(args, dry_run)

    def list_tools(self) -> list[dict[str, Any]]:
        return [self._defs[k] for k in sorted(self._defs.keys())]

