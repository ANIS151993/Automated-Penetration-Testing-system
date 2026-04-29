from __future__ import annotations

from dataclasses import dataclass

from app.agents.nodes.tool_caller import wrap_step_output_for_prompt
from app.agents.prompts import VULN_MAPPER_SYSTEM
from app.agents.state import EngagementState, Phase
from app.core.llm_client import LLMClient, LLMError
from app.knowledge.service import KnowledgeService

ALLOWED_SEVERITIES: frozenset[str] = frozenset(
    {"info", "low", "medium", "high", "critical"}
)
MAX_CANDIDATES = 8
KB_TOP_K = 4
KB_MIN_SCORE = 0.15
TOOL_OUTPUT_BUDGET_CHARS = 12000


@dataclass(slots=True)
class VulnMapperDeps:
    llm: LLMClient
    knowledge: KnowledgeService | None = None


def _format_step_outputs(state: EngagementState) -> str:
    if not state.step_results:
        return "(no prior tool output)\n"
    blocks: list[str] = []
    used = 0
    for result in state.step_results:
        if result.status != "completed":
            continue
        ref_id = result.invocation_id or result.execution_id or ""
        header = (
            f"[ref={ref_id}] {result.tool_name}.{result.operation_name}"
            if ref_id
            else f"{result.tool_name}.{result.operation_name}"
        )
        block = f"{header}\n{wrap_step_output_for_prompt(result)}"
        if used + len(block) > TOOL_OUTPUT_BUDGET_CHARS:
            blocks.append("(...output truncated for context budget...)")
            break
        blocks.append(block)
        used += len(block)
    return "\n".join(blocks) if blocks else "(no successful tool output)\n"


def _collect_known_refs(state: EngagementState) -> set[str]:
    refs: set[str] = set()
    for result in state.step_results:
        if result.invocation_id:
            refs.add(result.invocation_id)
        if result.execution_id:
            refs.add(result.execution_id)
    return refs


def _validate_candidate(
    raw: dict,
    known_refs: set[str],
    default_citations: list[str],
) -> dict:
    title = raw.get("title")
    severity = raw.get("severity")
    technique = raw.get("attack_technique")
    summary = raw.get("summary")
    refs_raw = raw.get("evidence_refs")
    citations_raw = raw.get("citations")

    if not isinstance(title, str) or not title.strip():
        raise LLMError(f"vuln candidate missing title: {raw!r}")
    if severity not in ALLOWED_SEVERITIES:
        raise LLMError(f"vuln candidate has invalid severity {severity!r}")
    if not isinstance(technique, str) or not technique.strip():
        raise LLMError(f"vuln candidate missing attack_technique: {raw!r}")
    if not isinstance(summary, str) or not summary.strip():
        raise LLMError(f"vuln candidate missing summary: {raw!r}")
    if not isinstance(refs_raw, list) or not refs_raw:
        raise LLMError(f"vuln candidate missing evidence_refs: {raw!r}")

    refs = [str(r) for r in refs_raw if isinstance(r, (str, bytes))]
    if known_refs and not any(r in known_refs for r in refs):
        raise LLMError(
            f"vuln candidate cites unknown evidence refs {refs!r}"
        )

    if isinstance(citations_raw, list):
        citations = [str(c) for c in citations_raw if isinstance(c, (str, bytes))]
    else:
        citations = list(default_citations)

    return {
        "title": title.strip(),
        "severity": severity,
        "attack_technique": technique.strip(),
        "summary": summary.strip(),
        "evidence_refs": refs,
        "citations": citations,
    }


async def map_vulnerabilities(
    state: EngagementState,
    deps: VulnMapperDeps,
) -> EngagementState:
    reference_block = ""
    default_citations: list[str] = []
    if deps.knowledge is not None:
        query = (
            f"{state.operator_goal}\n{state.intent}\nvulnerability mapping"
        ).strip()
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
        "Prior tool output:\n"
        f"{_format_step_outputs(state)}\n"
        "Identify vulnerability candidates supported by this evidence."
    )

    result = await deps.llm.complete_json(
        "map_vulnerability",
        user_message,
        system_prompt=VULN_MAPPER_SYSTEM,
    )
    raw_candidates = (
        result.get("candidates") if isinstance(result, dict) else None
    )
    if not isinstance(raw_candidates, list):
        raise LLMError(f"vuln mapper returned no candidates list: {result!r}")

    known_refs = _collect_known_refs(state)
    findings: list[dict] = []
    for raw in raw_candidates[:MAX_CANDIDATES]:
        if not isinstance(raw, dict):
            raise LLMError(f"vuln candidate is not an object: {raw!r}")
        findings.append(_validate_candidate(raw, known_refs, default_citations))

    state.findings = findings
    state.current_phase = Phase.VULN_MAPPING
    return state


__all__ = ["VulnMapperDeps", "map_vulnerabilities", "ALLOWED_SEVERITIES"]
