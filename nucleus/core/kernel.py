from __future__ import annotations

from typing import Any, Dict, Optional
from pathlib import Path

from nucleus.registry.tool_registry import ToolRegistry
from nucleus.trace.trace_emitter import TraceEmitter
from nucleus.trace.trace_store_jsonl import TraceStoreJSONL
from nucleus.contract_store import ContractStore
from nucleus.resources import core_contracts_schemas_dir

from .executor import Executor
from .planner import Planner
from .errors import PolicyDenied
from .policy_engine import PolicyEngine
from .runtime_context import RuntimeContext


_CORE_CONTRACTS: Optional[ContractStore] = None


def _core_contracts() -> ContractStore:
    global _CORE_CONTRACTS
    if _CORE_CONTRACTS is None:
        store = ContractStore(core_contracts_schemas_dir())
        store.load()
        _CORE_CONTRACTS = store
    return _CORE_CONTRACTS


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

        # Contract validation (public API): plan must validate before any policy/execution.
        plan_errors = _core_contracts().validate("plan.schema.json", plan)
        if plan_errors:
            trace.emit(
                "error",
                intent_id=intent_id,
                plan_id=plan_id,
                message="Plan schema validation failed",
                data={"errors": plan_errors},
            )
            from .errors import ValidationError  # local import to avoid cycles

            raise ValidationError(
                code="plan.schema_invalid",
                message="Plan does not validate against contracts/core plan.schema.json",
                data={"errors": plan_errors},
            )

        policy_engine = PolicyEngine(self._tools)
        result = policy_engine.evaluate(ctx, plan)
        trace.emit(
            "policy_decision",
            intent_id=intent_id,
            plan_id=plan_id,
            policy={"decision": result.decision, "reason_codes": result.reason_codes, "summary": result.summary},
        )
        if result.decision != "allow":
            trace.emit(
                "step_denied",
                intent_id=intent_id,
                plan_id=plan_id,
                message=result.summary or "Denied by policy",
                policy={"decision": result.decision, "reason_codes": result.reason_codes, "summary": result.summary},
            )
            raise PolicyDenied(
                code="policy.denied",
                message=result.summary or "Denied by policy",
                data={"reasons": result.reason_codes},
            )

        executor = Executor(self._tools, trace)
        return executor.execute(ctx, plan)

