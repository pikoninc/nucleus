from __future__ import annotations

from typing import Any, Dict

from .policy_engine import PolicyEngine, PolicyResult
from .runtime_context import RuntimeContext


class PermissionGuard:
    """
    Final, non-bypassable gate before execution.

    Invariant:
    - deny-by-default when policy is not allow.
    """

    def __init__(self, policy: PolicyEngine):
        self._policy = policy

    def check(self, ctx: RuntimeContext, plan: Dict[str, Any]) -> PolicyResult:
        result = self._policy.evaluate(ctx, plan)
        self._policy.require_allow(result)
        return result

