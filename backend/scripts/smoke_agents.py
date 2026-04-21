"""Live smoke test for the PentAI agent chain against real Ollama.

Runs classify + plan_recon + a fake tool-caller against a staged engagement
state. The executor is a stub so this does NOT hit the weapon gateway — it
just proves the LLM routing + JSON schema enforcement work end to end.

Usage (from backend/, with Ollama reachable at $OLLAMA_URL):
    uv run python scripts/smoke_agents.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from app.agents.nodes.tool_caller import ExecutorResult, ToolCallerDeps
from app.agents.state import EngagementState, PlannedStep
from app.agents.supervisor import SupervisorDeps, run_recon_pipeline
from app.core.llm_client import LLMClient


async def _fake_executor(step: PlannedStep) -> ExecutorResult:
    return ExecutorResult(
        status="skipped",
        exit_code=None,
        stdout=f"(smoke) would run {step.tool_name}.{step.operation_name} "
        f"with {step.args}",
        stderr="",
        invocation_id=f"smoke-{step.tool_name}",
    )


async def main() -> int:
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    print(f"[smoke] using ollama at {ollama_url}")

    async with LLMClient(ollama_url) as llm:
        state = EngagementState(
            engagement_id="smoke-eng",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal=(
                "Scan 172.20.32.59 for open TCP services on common ports "
                "(22, 80, 443) so we can enumerate the target."
            ),
        )
        deps = SupervisorDeps(
            llm=llm,
            tool_caller=ToolCallerDeps(executor=_fake_executor),
        )
        out = await run_recon_pipeline(state, deps)

    print(f"[smoke] classified intent: {out.intent}")
    print(f"[smoke] planned {len(out.planned_steps)} steps:")
    for idx, step in enumerate(out.planned_steps, 1):
        print(
            f"  {idx}. {step.tool_name}.{step.operation_name} "
            f"args={step.args} reason={step.reason!r}"
        )
    print(f"[smoke] executed {len(out.step_results)} stub results")
    if out.errors:
        print(f"[smoke] errors: {out.errors}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
