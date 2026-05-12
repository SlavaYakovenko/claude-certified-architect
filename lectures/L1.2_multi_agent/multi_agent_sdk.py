"""
L1.2 (Bonus): Multi-Agent via claude-agent-sdk
===============================================
Shows the SAME coordinator pattern using claude-agent-sdk
(which wraps the Claude Code CLI under the hood).

With the SDK, Task is a BUILT-IN tool — we do NOT define it in input_schema.
We only grant permission: allowed_tools=["Task"].
The SDK intercepts Task calls and runs isolated agent loops automatically.

Contrast with multi_agent.py, which uses the raw anthropic API
and implements Task-equivalent manually with spawn_*_agent() functions.

Requirements:
    pip install claude-agent-sdk
    Claude Code CLI must be installed: https://claude.ai/download
"""

import asyncio
import claude_agent_sdk
from claude_agent_sdk import ClaudeAgentOptions


async def run_coordinator_sdk(research_topic: str) -> None:
    """
    Runs a multi-agent coordinator via claude-agent-sdk.

    The coordinator prompt instructs Claude to spawn subagents using Task.
    Claude Code internally handles Task calls — spawning isolated agent loops,
    collecting results, and returning them to the coordinator.
    """
    print(f"\n{'='*60}")
    print(f"Research topic: {research_topic}")
    print(f"Using: claude-agent-sdk (wraps Claude Code CLI)")
    print(f"{'='*60}\n")

    options = ClaudeAgentOptions(
        # Task is built-in — we only grant permission here
        # We do NOT define it in any input_schema
        allowed_tools=["Task"],
        system_prompt=(
            "You are a research coordinator. "
            "Decompose the given topic into 3 subtopics. "
            "Use the Task tool to spawn a separate research subagent for each subtopic. "
            "Each subagent should search for relevant information. "
            "After all subagents complete, synthesize their findings into a final report."
        ),
        max_turns=20,
        permission_mode="bypassPermissions",  # allow Task without interactive prompts
    )

    # query() is an async generator — yields Message objects as they arrive
    async for msg in claude_agent_sdk.query(
        prompt=f"Research: {research_topic}",
        options=options,
    ):
        msg_type = type(msg).__name__

        if msg_type == "AssistantMessage":
            # Print text blocks from assistant responses
            for block in msg.content:
                if hasattr(block, "text"):
                    print(f"[Coordinator] {block.text[:300]}")
                elif hasattr(block, "type") and block.type == "tool_use":
                    # Task calls appear as tool_use blocks
                    print(f"  → Spawning subagent via Task: {str(block.input)[:100]}")

        elif msg_type == "ResultMessage":
            print(f"\n[Done] turns={msg.num_turns}, cost=${msg.total_cost_usd:.4f}")


if __name__ == "__main__":
    asyncio.run(run_coordinator_sdk("AI impact on creative industries"))
