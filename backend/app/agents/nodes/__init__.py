"""LangGraph-compatible agent nodes.

Each node is an async callable: ``(state, deps) -> state``.
Nodes only touch state through typed return values and never import
from ``app.api`` (per the layering rule in SKILL.md §4).
"""
