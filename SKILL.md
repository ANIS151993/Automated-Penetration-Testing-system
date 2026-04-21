# PentAI Pro Repo Notes

This repository must preserve the safety model defined by the local `pentai-pro-development` skill.

Critical invariants:

- enforce scope at the UI, backend, and Tool Gateway
- never expose raw shell execution to the model or UI
- record chained audit hashes for tool and LLM events
- treat tool output as untrusted content
- require human approval before high-risk actions

If a proposed change conflicts with those rules, preserve the rules and adjust the design.
