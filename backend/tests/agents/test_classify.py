from __future__ import annotations

import json

import httpx
import pytest

from app.agents.nodes.classify import ClassifyDeps, classify_intent
from app.agents.state import EngagementState
from app.core.llm_client import LLMClient, LLMError


@pytest.mark.asyncio
async def test_classify_intent_happy_path():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "intent": "recon_and_enum",
                            "justification": "Operator asked for open ports and versions.",
                        }
                    ),
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="Find open services on 172.20.32.59",
        )
        out = await classify_intent(state, ClassifyDeps(llm=llm))
        assert out.intent == "recon_and_enum"


@pytest.mark.asyncio
async def test_classify_intent_rejects_unknown_label():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"intent": "pwn_everything"}),
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="goal",
        )
        with pytest.raises(LLMError):
            await classify_intent(state, ClassifyDeps(llm=llm))
