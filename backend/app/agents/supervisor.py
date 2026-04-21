from __future__ import annotations

from dataclasses import dataclass

from app.agents.nodes.classify import ClassifyDeps, classify_intent
from app.agents.nodes.recon_planner import PlannerDeps, plan_recon
from app.agents.nodes.tool_caller import ToolCallerDeps, call_tools
from app.agents.state import EngagementState, Phase
from app.core.llm_client import LLMClient, LLMError

RECON_INTENTS = frozenset({"recon_only", "recon_and_enum", "full_pentest"})


@dataclass(slots=True)
class SupervisorDeps:
    llm: LLMClient
    tool_caller: ToolCallerDeps


async def run_recon_pipeline(
    state: EngagementState,
    deps: SupervisorDeps,
) -> EngagementState:
    state = await classify_intent(state, ClassifyDeps(llm=deps.llm))
    if state.intent not in RECON_INTENTS:
        raise LLMError(
            f"intent {state.intent!r} does not authorize reconnaissance actions"
        )
    state = await plan_recon(state, PlannerDeps(llm=deps.llm))
    state = await call_tools(state, deps.tool_caller)
    state.current_phase = Phase.RECONNAISSANCE
    return state
