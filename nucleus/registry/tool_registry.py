from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


ToolFunc = Callable[[Dict[str, Any], bool], Dict[str, Any]]


class ToolRegistry:
    """
    Registry for deterministic tools and their metadata.
    """

    def __init__(self) -> None:
        self._defs: Dict[str, Dict[str, Any]] = {}
        self._impls: Dict[str, ToolFunc] = {}

    def register(self, tool_def: Dict[str, Any], impl: ToolFunc) -> None:
        tool_id = tool_def["tool_id"]
        self._defs[tool_id] = tool_def
        self._impls[tool_id] = impl

    def get(self, tool_id: str) -> Optional[Dict[str, Any]]:
        return self._defs.get(tool_id)

    def call(self, tool_id: str, args: Dict[str, Any], *, dry_run: bool) -> Dict[str, Any]:
        impl = self._impls.get(tool_id)
        if impl is None:
            raise KeyError(tool_id)
        return impl(args, dry_run)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [self._defs[k] for k in sorted(self._defs.keys())]

