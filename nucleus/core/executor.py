from __future__ import annotations

from typing import Any, Dict, List, Optional

import jsonschema

from .errors import ToolExecutionError, ToolNotFound, ValidationError
from .runtime_context import RuntimeContext
from ..registry.tool_registry import ToolRegistry
from ..trace.trace_emitter import TraceEmitter


class Executor:
    """
    Executes a validated plan step-by-step via deterministic tools.
    Always emits trace events for auditing.
    """

    def __init__(self, tool_registry: ToolRegistry, trace: TraceEmitter):
        self._tools = tool_registry
        self._trace = trace

    def execute(self, ctx: RuntimeContext, plan: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(plan, dict):
            raise ValidationError(code="plan.invalid", message="Plan must be an object")

        plan_id = plan.get("plan_id")
        if not isinstance(plan_id, str) or not plan_id:
            raise ValidationError(code="plan.invalid", message="plan_id must be a non-empty string")

        intent = plan.get("intent") if isinstance(plan.get("intent"), dict) else {}
        intent_id = intent.get("intent_id") if isinstance(intent.get("intent_id"), str) else None  # type: Optional[str]

        steps = plan.get("steps")
        if not isinstance(steps, list) or len(steps) < 1:
            raise ValidationError(code="plan.invalid", message="Plan.steps must be a non-empty array")

        self._trace.emit("plan_generated", intent_id=intent_id, plan_id=plan_id, message="Plan ready for execution")

        results = []  # type: List[Dict[str, Any]]
        for step in steps:
            if not isinstance(step, dict):
                raise ValidationError(code="plan.step_invalid", message="Step must be an object")
            step_id = step.get("step_id")
            if not isinstance(step_id, str) or not step_id:
                raise ValidationError(code="plan.step_invalid", message="step_id is required")

            tool_call = step.get("tool")
            if not isinstance(tool_call, dict):
                raise ValidationError(code="plan.step_invalid", message="Step.tool is required")
            tool_id = tool_call.get("tool_id")
            args = tool_call.get("args")
            if not isinstance(tool_id, str) or not tool_id:
                raise ValidationError(code="plan.step_invalid", message="tool_id is required")
            if not isinstance(args, dict):
                raise ValidationError(code="plan.step_invalid", message="args must be an object")

            tool_def = self._tools.get(tool_id)
            if tool_def is None:
                self._trace.emit(
                    "step_denied",
                    intent_id=intent_id,
                    plan_id=plan_id,
                    step_id=step_id,
                    message="Unknown tool",
                    data={"tool_id": tool_id},
                )
                raise ToolNotFound(code="tool.unknown", message=f"Unknown tool: {tool_id}", data={"tool_id": tool_id})

            # Validate tool args against tool args_schema for better, stable errors.
            try:
                args_schema = tool_def.get("args_schema", {})
                jsonschema.Draft202012Validator(args_schema).validate(args)
            except Exception as e:  # noqa: BLE001
                self._trace.emit(
                    "step_denied",
                    intent_id=intent_id,
                    plan_id=plan_id,
                    step_id=step_id,
                    message="Tool args validation failed",
                    data={"tool_id": tool_id, "error": repr(e)},
                )
                raise ValidationError(
                    code="tool.args_invalid",
                    message="Tool args validation failed",
                    data={"tool_id": tool_id},
                ) from e

            self._trace.emit(
                "step_started",
                intent_id=intent_id,
                plan_id=plan_id,
                step_id=step_id,
                message="Step started",
                data={"tool_id": tool_id, "dry_run": ctx.dry_run},
            )
            try:
                out = self._tools.call(tool_id, args, dry_run=ctx.dry_run)
                results.append({"step_id": step_id, "tool_id": tool_id, "output": out})
                self._trace.emit(
                    "step_finished",
                    intent_id=intent_id,
                    plan_id=plan_id,
                    step_id=step_id,
                    message="Step finished",
                    data={"tool_id": tool_id, "ok": True, "output": out},
                )
            except Exception as e:  # noqa: BLE001
                self._trace.emit(
                    "error",
                    intent_id=intent_id,
                    plan_id=plan_id,
                    step_id=step_id,
                    message="Tool execution error",
                    data={"tool_id": tool_id, "error": repr(e)},
                )
                raise ToolExecutionError(code="tool.error", message="Tool execution error", data={"tool_id": tool_id}) from e

        self._trace.emit("run_finished", intent_id=intent_id, plan_id=plan_id, message="Run finished", data={"ok": True})
        return {"plan_id": plan_id, "results": results}

