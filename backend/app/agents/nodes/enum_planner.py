from __future__ import annotations

from dataclasses import dataclass

from app.agents.nodes.recon_planner import (
    ALLOWED_TOOLS,
    MAX_STEPS,
    _validate_step,
)
from app.agents.nodes.tool_caller import wrap_step_output_for_prompt
from app.agents.prompts import ENUM_PLANNER_SYSTEM
from app.agents.state import EngagementState, Phase, PlannedStep
from app.core.llm_client import LLMClient, LLMError
from app.knowledge.service import KnowledgeService

KB_TOP_K = 4
KB_MIN_SCORE = 0.15
RECON_OUTPUT_BUDGET_CHARS = 8000


@dataclass(slots=True)
class EnumPlannerDeps:
    llm: LLMClient
    knowledge: KnowledgeService | None = None


def _format_recon_outputs(state: EngagementState) -> str:
    if not state.step_results:
        return "(no prior reconnaissance output)\n"
    blocks: list[str] = []
    used = 0
    for result in state.step_results:
        if result.status != "completed":
            continue
        block = wrap_step_output_for_prompt(result)
        if used + len(block) > RECON_OUTPUT_BUDGET_CHARS:
            blocks.append("(...recon output truncated for context budget...)")
            break
        blocks.append(block)
        used += len(block)
    return "\n".join(blocks) if blocks else "(no successful recon output)\n"


async def plan_enumeration(
    state: EngagementState,
    deps: EnumPlannerDeps,
) -> EngagementState:
    reference_block = ""
    default_citations: list[str] = []
    if deps.knowledge is not None:
        query = f"{state.operator_goal}\n{state.intent}\nenumeration".strip()
        chunks = await deps.knowledge.search(
            query, top_k=KB_TOP_K, min_score=KB_MIN_SCORE
        )
        if chunks:
            from app.knowledge.retrieval import format_context

            seen: set[str] = set()
            for chunk in chunks:
                if chunk.source_path not in seen:
                    seen.add(chunk.source_path)
                    default_citations.append(chunk.source_path)
            reference_block = (
                "Reference material:\n" + format_context(chunks) + "\n\n"
            )

    user_message = (
        f"{reference_block}"
        f"OPERATOR goal: {state.operator_goal}\n"
        f"OPERATOR scope CIDRs: {state.scope_cidrs}\n"
        f"OPERATOR intent: {state.intent}\n"
        "Prior reconnaissance output:\n"
        f"{_format_recon_outputs(state)}\n"
        "Plan up to 5 enumeration steps that deepen the inventory."
    )

    result = await deps.llm.complete_json(
        "plan_enumeration",
        user_message,
        system_prompt=ENUM_PLANNER_SYSTEM,
    )
    steps_raw = result.get("steps") if isinstance(result, dict) else None
    if not isinstance(steps_raw, list) or not steps_raw:
        raise LLMError(f"enum planner returned no steps: {result!r}")

    steps: list[PlannedStep] = []
    for raw in steps_raw[:MAX_STEPS]:
        if not isinstance(raw, dict):
            raise LLMError(f"enum planner step is not an object: {raw!r}")
        step = _validate_step(raw, state.scope_cidrs, default_citations)
        step.phase = Phase.ENUMERATION
        steps.append(step)

    state.planned_steps = steps
    state.current_phase = Phase.ENUMERATION
    return state


__all__ = ["EnumPlannerDeps", "plan_enumeration", "ALLOWED_TOOLS"]
