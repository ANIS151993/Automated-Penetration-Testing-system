from __future__ import annotations

from dataclasses import dataclass

from app.agents.prompts import CLASSIFY_SYSTEM
from app.agents.state import EngagementState
from app.core.llm_client import LLMClient, LLMError

ALLOWED_INTENTS: frozenset[str] = frozenset(
    {
        "recon_only",
        "recon_and_enum",
        "full_pentest",
        "targeted_check",
        "unsupported",
    }
)


@dataclass(slots=True)
class ClassifyDeps:
    llm: LLMClient


async def classify_intent(
    state: EngagementState,
    deps: ClassifyDeps,
) -> EngagementState:
    user_message = (
        f"OPERATOR goal: {state.operator_goal}\n"
        f"OPERATOR scope CIDRs: {state.scope_cidrs}\n"
    )
    result = await deps.llm.complete_json(
        "classify",
        user_message,
        system_prompt=CLASSIFY_SYSTEM,
    )
    intent = result.get("intent") if isinstance(result, dict) else None
    if intent not in ALLOWED_INTENTS:
        raise LLMError(
            f"Classifier returned invalid intent {intent!r}. Raw response: {result!r}"
        )
    state.intent = intent
    return state
