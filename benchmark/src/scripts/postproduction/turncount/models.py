"""Pydantic models for turn count data."""

from pydantic import BaseModel, Field


class SubagentTurnCounts(BaseModel):
    """Turn and tool call counts for a single subagent conversation."""

    turns: int = Field(
        description="Number of assistant messages (LLM generation rounds)"
    )
    tool_calls: int = Field(description="Number of tool role messages (tool responses)")


class TurnCounts(BaseModel):
    """Aggregated turn counts across all subagents for a sample."""

    impl: SubagentTurnCounts = Field(
        default_factory=lambda: SubagentTurnCounts(turns=0, tool_calls=0),
        description="Turn counts for implementation agent",
    )
    spec: SubagentTurnCounts = Field(
        default_factory=lambda: SubagentTurnCounts(turns=0, tool_calls=0),
        description="Turn counts for specification agent",
    )
    units: SubagentTurnCounts = Field(
        default_factory=lambda: SubagentTurnCounts(turns=0, tool_calls=0),
        description="Turn counts for units agent",
    )
    total_turns: int = Field(description="Sum of turns across all subagents")
    total_tool_calls: int = Field(description="Sum of tool calls across all subagents")
