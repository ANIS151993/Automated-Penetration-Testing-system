from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse

from app.agents.prompts import RECON_PLANNER_SYSTEM
from app.agents.state import EngagementState, Phase, PlannedStep
from app.core.llm_client import LLMClient, LLMError

ALLOWED_TOOLS: dict[str, frozenset[str]] = {
    "nmap": frozenset({"service_scan", "os_detection"}),
    "http_probe": frozenset({"fetch_headers"}),
}

MAX_STEPS = 5


@dataclass(slots=True)
class PlannerDeps:
    llm: LLMClient


def _target_in_scope(target: str, scope_cidrs: list[str]) -> bool:
    try:
        ip = ip_address(target)
    except ValueError:
        return False
    return any(ip in ip_network(cidr, strict=False) for cidr in scope_cidrs)


def _url_host_in_scope(url: str, scope_cidrs: list[str]) -> bool:
    host = urlparse(url).hostname
    return bool(host) and _target_in_scope(host, scope_cidrs)


def _validate_step(raw: dict, scope_cidrs: list[str]) -> PlannedStep:
    tool_name = raw.get("tool_name")
    operation_name = raw.get("operation_name")
    args = raw.get("args") or {}
    reason = raw.get("reason") or ""

    if tool_name not in ALLOWED_TOOLS:
        raise LLMError(f"planner proposed unknown tool {tool_name!r}")
    if operation_name not in ALLOWED_TOOLS[tool_name]:
        raise LLMError(
            f"planner proposed unknown operation {tool_name}.{operation_name}"
        )
    if "target" in args and not _target_in_scope(args["target"], scope_cidrs):
        raise LLMError(
            f"planner proposed out-of-scope target {args['target']!r}"
        )
    if "url" in args and not _url_host_in_scope(args["url"], scope_cidrs):
        raise LLMError(f"planner proposed out-of-scope URL {args['url']!r}")

    return PlannedStep(
        tool_name=tool_name,
        operation_name=operation_name,
        args=args,
        reason=reason,
        phase=Phase.RECONNAISSANCE,
    )


async def plan_recon(
    state: EngagementState,
    deps: PlannerDeps,
) -> EngagementState:
    user_message = (
        f"OPERATOR goal: {state.operator_goal}\n"
        f"OPERATOR scope CIDRs: {state.scope_cidrs}\n"
        f"OPERATOR intent: {state.intent}\n"
        "Plan up to 5 reconnaissance steps."
    )
    result = await deps.llm.complete_json(
        "plan_recon",
        user_message,
        system_prompt=RECON_PLANNER_SYSTEM,
    )
    steps_raw = result.get("steps") if isinstance(result, dict) else None
    if not isinstance(steps_raw, list) or not steps_raw:
        raise LLMError(f"planner returned no steps: {result!r}")

    steps: list[PlannedStep] = []
    for raw in steps_raw[:MAX_STEPS]:
        if not isinstance(raw, dict):
            raise LLMError(f"planner step is not an object: {raw!r}")
        steps.append(_validate_step(raw, state.scope_cidrs))

    state.planned_steps = steps
    state.current_phase = Phase.RECONNAISSANCE
    return state
