from __future__ import annotations

from dataclasses import dataclass

from app.agents.nodes.classify import ClassifyDeps, classify_intent
from app.agents.nodes.enum_planner import EnumPlannerDeps, plan_enumeration
from app.agents.nodes.exploit_planner import ExploitPlannerDeps, plan_exploitation
from app.agents.nodes.recon_planner import PlannerDeps, plan_recon
from app.agents.nodes.tool_caller import ToolCallerDeps, call_tools
from app.agents.nodes.vuln_mapper import VulnMapperDeps, map_vulnerabilities
from app.agents.state import EngagementState, Phase
from app.core.llm_client import LLMClient, LLMError
from app.knowledge.service import KnowledgeService

RECON_INTENTS = frozenset({"recon_only", "recon_and_enum", "full_pentest"})
ENUM_INTENTS = frozenset({"recon_and_enum", "full_pentest"})
VULN_INTENTS = frozenset({"full_pentest", "targeted_check"})
EXPLOIT_INTENTS = frozenset({"full_pentest"})


@dataclass(slots=True)
class SupervisorDeps:
    llm: LLMClient
    tool_caller: ToolCallerDeps
    knowledge: KnowledgeService | None = None


async def run_recon_pipeline(
    state: EngagementState,
    deps: SupervisorDeps,
) -> EngagementState:
    state = await classify_intent(state, ClassifyDeps(llm=deps.llm))
    if state.intent not in RECON_INTENTS:
        raise LLMError(
            f"intent {state.intent!r} does not authorize reconnaissance actions"
        )
    state = await plan_recon(
        state, PlannerDeps(llm=deps.llm, knowledge=deps.knowledge)
    )
    state = await call_tools(state, deps.tool_caller)
    state.current_phase = Phase.RECONNAISSANCE
    return state


async def run_recon_and_enum_pipeline(
    state: EngagementState,
    deps: SupervisorDeps,
) -> EngagementState:
    state = await run_recon_pipeline(state, deps)
    if state.intent not in ENUM_INTENTS:
        return state
    state = await plan_enumeration(
        state, EnumPlannerDeps(llm=deps.llm, knowledge=deps.knowledge)
    )
    state = await call_tools(state, deps.tool_caller)
    state.current_phase = Phase.ENUMERATION
    return state


async def run_full_pipeline(
    state: EngagementState,
    deps: SupervisorDeps,
) -> EngagementState:
    state = await run_recon_and_enum_pipeline(state, deps)
    if state.intent not in VULN_INTENTS:
        return state
    state = await map_vulnerabilities(
        state, VulnMapperDeps(llm=deps.llm, knowledge=deps.knowledge)
    )
    if state.intent in EXPLOIT_INTENTS and state.findings:
        state = await plan_exploitation(
            state,
            ExploitPlannerDeps(llm=deps.llm, knowledge=deps.knowledge),
        )
    return state
