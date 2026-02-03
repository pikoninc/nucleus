from __future__ import annotations

from typing import Any, Dict, Optional

from nucleus.registry.tool_registry import ToolRegistry
from nucleus.trace.trace_emitter import TraceEmitter
from nucleus.trace.trace_store_jsonl import TraceStoreJSONL

from .executor import Executor
from .permission_guard import PermissionGuard
from .planner import Planner
from .policy_engine import PolicyEngine, PolicyResult
from .runtime_context import RuntimeContext


class Kernel:
    """
    Minimal kernel orchestration: Intent -> Plan -> Policy -> Execute -> Trace.

    Hard rules:
    - plan-first gating: execution always happens from a Plan object.
    - deterministic tools only (no arbitrary shell).
    - trace every step.
    """

    def __init__(self, tool_registry: ToolRegistry):
        self._tools = tool_registry

    def run_intent(self, ctx: RuntimeContext, intent: Dict[str, Any], planner: Planner) -> Dict[str, Any]:
        plan = planner.plan(intent)
        return self.run_plan(ctx, plan)

    def run_plan(self, ctx: RuntimeContext, plan: Dict[str, Any]) -> Dict[str, Any]:
        store = TraceStoreJSONL(ctx.trace_path)
        trace = TraceEmitter(store=store, run_id=ctx.run_id)

        intent = plan.get("intent") if isinstance(plan.get("intent"), dict) else {}
        intent_id = intent.get("intent_id") if isinstance(intent.get("intent_id"), str) else None  # type: Optional[str]
        plan_id = plan.get("plan_id") if isinstance(plan.get("plan_id"), str) else None

        trace.emit("intent_received", intent_id=intent_id, plan_id=plan_id, message="Intent received", data={"intent": intent})

        policy_engine = PolicyEngine(self._tools)
        guard = PermissionGuard(policy_engine)
        result = guard.check(ctx, plan)
        trace.emit(
            "policy_decision",
            intent_id=intent_id,
            plan_id=plan_id,
            policy={"decision": result.decision, "reason_codes": result.reason_codes, "summary": result.summary},
        )

        executor = Executor(self._tools, trace)
        return executor.execute(ctx, plan)

