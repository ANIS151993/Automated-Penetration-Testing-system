from __future__ import annotations

import json

import httpx
import pytest

from app.core.llm_client import (
    MODEL_ROUTING,
    LLMClient,
    LLMError,
    format_tool_output_for_prompt,
)


def _chat_responder(payload: dict) -> httpx.Response:
    assert payload["messages"][0]["role"] == "system"
    assert "untrusted" in payload["messages"][0]["content"]
    return httpx.Response(
        200,
        json={
            "model": payload["model"],
            "message": {
                "role": "assistant",
                "content": json.dumps({"ok": True, "model": payload["model"]}),
            },
        },
    )


@pytest.mark.asyncio
async def test_complete_routes_task_to_correct_model():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_responder(json.loads(request.content))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient("http://ollama", client=http_client)
        for task, expected_model in MODEL_ROUTING.items():
            if task == "embed":
                continue
            raw = await client.complete(task, "OPERATOR: ping")
            assert json.loads(raw)["model"] == expected_model


@pytest.mark.asyncio
async def test_complete_json_returns_parsed_object():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["format"] == "json"
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": '{"x":1,"y":2}'},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient("http://ollama", client=http_client)
        result = await client.complete_json("classify", "OPERATOR: hi")
        assert result == {"x": 1, "y": 2}


@pytest.mark.asyncio
async def test_complete_json_raises_on_non_json_content():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "not json"}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient("http://ollama", client=http_client)
        with pytest.raises(LLMError):
            await client.complete_json("classify", "OPERATOR: hi")


@pytest.mark.asyncio
async def test_unknown_task_raises_key_error():
    transport = httpx.MockTransport(lambda _: httpx.Response(500))
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient("http://ollama", client=http_client)
        with pytest.raises(KeyError):
            await client.complete("definitely-not-a-task", "OPERATOR: hi")


def test_format_tool_output_wraps_in_untrusted_tags():
    wrapped = format_tool_output_for_prompt("nmap", "22/tcp open")
    assert wrapped.startswith('<tool_output trust="untrusted" tool="nmap">')
    assert wrapped.endswith("</tool_output>")
    assert "22/tcp open" in wrapped


def test_system_prompt_prefix_instructs_injection_defense():
    from app.core.llm_client import SYSTEM_PROMPT_PREFIX

    assert "untrusted" in SYSTEM_PROMPT_PREFIX
    assert "never execute shell" in SYSTEM_PROMPT_PREFIX.lower()
