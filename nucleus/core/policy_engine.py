from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .errors import PolicyDenied, ValidationError
from .runtime_context import RuntimeContext
from .scope import is_within_any_root, normalize_roots
from ..registry.tool_registry import ToolRegistry


@dataclass(frozen=True)
class PolicyResult:
    decision: str  # allow|deny
    reason_codes: List[str]
    summary: Optional[str] = None


class PolicyEngine:
    """
    Enforces safety invariants and authorization decisions.

    Minimum enforced invariants:
    - explicit scope required
    - no destructive operations by default
    - strict dry-run compatibility when enabled
    - tool must exist in registry
    """

    def __init__(self, tool_registry: ToolRegistry):
        self._tools = tool_registry

    def evaluate(self, ctx: RuntimeContext, plan: Dict[str, Any]) -> PolicyResult:
        reasons: List[str] = []

        intent = plan.get("intent")
        if not isinstance(intent, dict):
            return PolicyResult(decision="deny", reason_codes=["plan.intent_missing"], summary="Plan is missing intent")

        scope = intent.get("scope")
        if not isinstance(scope, dict) or not isinstance(scope.get("fs_roots"), list) or len(scope["fs_roots"]) < 1:
            return PolicyResult(decision="deny", reason_codes=["scope.missing"], summary="Explicit scope is required")

        roots = normalize_roots(scope.get("fs_roots", []))
        if len(roots) < 1:
            return PolicyResult(decision="deny", reason_codes=["scope.invalid"], summary="Scope fs_roots must be valid paths")

        allow_network = bool(scope.get("allow_network", False))
        network_hosts_allowlist = scope.get("network_hosts_allowlist", [])
        if network_hosts_allowlist is None:
            network_hosts_allowlist = []
        if not isinstance(network_hosts_allowlist, list) or any((not isinstance(x, str) or not x) for x in network_hosts_allowlist):
            return PolicyResult(
                decision="deny",
                reason_codes=["scope.invalid"],
                summary="Scope network_hosts_allowlist must be an array of non-empty strings when provided",
            )

        steps = plan.get("steps")
        if not isinstance(steps, list) or len(steps) < 1:
            return PolicyResult(decision="deny", reason_codes=["plan.steps_missing"], summary="Plan must have steps")

        for step in steps:
            if not isinstance(step, dict):
                return PolicyResult(decision="deny", reason_codes=["plan.step_invalid"], summary="Step must be an object")
            tool_call = step.get("tool")
            if not isinstance(tool_call, dict):
                return PolicyResult(decision="deny", reason_codes=["plan.tool_missing"], summary="Step.tool is required")
            tool_id = tool_call.get("tool_id")
            if not isinstance(tool_id, str) or not tool_id:
                return PolicyResult(decision="deny", reason_codes=["plan.tool_id_invalid"], summary="tool_id is required")

            tool_def = self._tools.get(tool_id)
            if tool_def is None:
                return PolicyResult(decision="deny", reason_codes=["tool.unknown"], summary=f"Unknown tool: {tool_id}")

            # Network safety: deny-by-default unless scope explicitly allows network.
            if tool_def.get("side_effects") == "network":
                if not allow_network:
                    return PolicyResult(
                        decision="deny",
                        reason_codes=["scope.network_denied"],
                        summary=f"Network tool is denied by scope.allow_network=false: {tool_id}",
                    )

                # Host allowlist is mandatory when network is enabled.
                if not network_hosts_allowlist:
                    return PolicyResult(
                        decision="deny",
                        reason_codes=["scope.network_allowlist_missing"],
                        summary="Network is enabled but scope.network_hosts_allowlist is empty",
                    )

                args_obj = tool_call.get("args", {})
                if not isinstance(args_obj, dict):
                    return PolicyResult(decision="deny", reason_codes=["plan.args_invalid"], summary="Step.tool.args must be an object")
                url = args_obj.get("url") or args_obj.get("endpoint")
                if not isinstance(url, str) or not url:
                    return PolicyResult(
                        decision="deny",
                        reason_codes=["scope.network_missing_url"],
                        summary=f"Network tool requires args.url or args.endpoint to enforce allowlist: {tool_id}",
                    )
                host = urlparse(url).hostname
                if not host:
                    return PolicyResult(
                        decision="deny",
                        reason_codes=["scope.network_invalid_url"],
                        summary=f"Invalid URL for network tool allowlist enforcement: {tool_id}",
                    )
                ok = False
                for pat in network_hosts_allowlist:
                    if pat == "*":
                        ok = True
                        break
                    if pat.startswith("*.") and host.endswith(pat[1:]):
                        ok = True
                        break
                    if host == pat:
                        ok = True
                        break
                if not ok:
                    return PolicyResult(
                        decision="deny",
                        reason_codes=["scope.network_host_denied"],
                        summary=f"Network host is not in allowlist: {host}",
                    )

            # Scope enforcement for filesystem tools: tool args must be within declared fs_roots.
            if isinstance(tool_id, str) and tool_id.startswith("fs."):
                # Common path keys:
                # - fs.list/fs.stat/fs.mkdir: path
                # - fs.move: from/to
                args_obj = tool_call.get("args", {})
                if not isinstance(args_obj, dict):
                    return PolicyResult(decision="deny", reason_codes=["plan.args_invalid"], summary="Step.tool.args must be an object")
                paths_to_check: List[str] = []
                for k in ("path", "from", "to"):
                    v = args_obj.get(k)
                    if isinstance(v, str) and v:
                        paths_to_check.append(v)
                for p in paths_to_check:
                    if not is_within_any_root(p, roots):
                        return PolicyResult(
                            decision="deny",
                            reason_codes=["scope.out_of_bounds"],
                            summary="Tool path outside declared scope: {}".format(p),
                        )

            if tool_def.get("destructive") and not ctx.allow_destructive:
                return PolicyResult(
                    decision="deny",
                    reason_codes=["tool.destructive_denied"],
                    summary=f"Destructive tool is denied by default: {tool_id}",
                )

            if ctx.dry_run and ctx.strict_dry_run and not tool_def.get("supports_dry_run", False):
                return PolicyResult(
                    decision="deny",
                    reason_codes=["dry_run.not_supported"],
                    summary=f"Tool does not support dry-run: {tool_id}",
                )

            if ctx.dry_run and tool_call.get("dry_run_ok") is False:
                return PolicyResult(
                    decision="deny",
                    reason_codes=["dry_run.step_not_marked_ok"],
                    summary=f"Step not marked dry-run compatible: {tool_id}",
                )

            reasons.append("tool.ok")

        return PolicyResult(decision="allow", reason_codes=["scope.ok", "tools.ok"], summary="Allowed by default policy")

    def require_allow(self, result: PolicyResult) -> None:
        if result.decision != "allow":
            raise PolicyDenied(
                code="policy.denied",
                message=result.summary or "Denied by policy",
                data={"reasons": result.reason_codes},
            )

