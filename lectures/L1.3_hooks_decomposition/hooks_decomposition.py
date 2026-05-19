"""
L1.3 - Hooks and Task Decomposition
=====================================
Demonstrates:
1. PostToolUse hook   - normalizing heterogeneous MCP tool output formats
2. PreToolUse hook    - blocking policy-violating tool calls (deny)
3. Hook registration  - ClaudeAgentOptions with typed hooks dict
4. Prompt chaining    - fixed sequential steps: draft -> critique -> improve
5. Dynamic decomp.    - coordinator decides how many subtasks based on content

Key insight:
- Hooks = deterministic interception (not probabilistic like prompt instructions)
- PreToolUse + "deny" = guaranteed block (not "please don't do X")
- PostToolUse + updatedMCPToolOutput = Claude sees normalized data, not raw

Requires: pip install claude-agent-sdk anthropic
"""

import asyncio
import json
from typing import Any

import anthropic
import claude_agent_sdk
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher
from claude_agent_sdk.types import (
    HookContext,
    HookJSONOutput,
    PostToolUseHookInput,
    PreToolUseHookInput,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PAYMENT_THRESHOLD = 10_000  # USD - payments above this require human approval

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Demo 1 & 2: Hooks
# ---------------------------------------------------------------------------

async def normalize_tool_output(
    hook_input: PostToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> HookJSONOutput:
    """
    PostToolUse hook: normalize MCP tool output to a unified format.

    Problem: different MCP tools return results under different field names:
      - search_web:     {"items": [...]}
      - query_database: {"rows": [...]}
      - fetch_api:      {"data": [...]}

    Solution: rewrite all to {"results": [...], "source": "<tool_type>"}
    before Claude receives the output. Claude always sees the same structure.
    """
    tool_name = hook_input["tool_name"]
    raw = hook_input["tool_response"]

    print(f"  [PostToolUse Hook] fired for: {tool_name}")

    FORMAT_MAP = {
        "search_web":     ("items",  "web"),
        "query_database": ("rows",   "db"),
        "fetch_api":      ("data",   "api"),
    }

    if tool_name not in FORMAT_MAP:
        return {}  # pass through unchanged - no update

    field, source = FORMAT_MAP[tool_name]
    normalized = {
        "results": raw.get(field, []),
        "source":  source,
        "count":   len(raw.get(field, [])),
    }
    print(f"  [PostToolUse Hook] '{field}' -> 'results', source={source}, count={normalized['count']}")

    return {
        "hookEventName": "PostToolUse",
        "updatedMCPToolOutput": normalized,  # Claude sees this instead of raw
    }


async def policy_enforcement_hook(
    hook_input: PreToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> HookJSONOutput:
    """
    PreToolUse hook: block tool calls that violate business policy.

    Checks payment amount before the tool executes.
    If above threshold -> deny (tool is NOT called, Claude gets refusal message).
    This is a programmatic guarantee, not a probabilistic prompt instruction.
    """
    tool_name = hook_input["tool_name"]
    tool_input = hook_input["tool_input"]

    print(f"  [PreToolUse Hook] fired for: {tool_name}")

    if tool_name == "execute_payment":
        amount = tool_input.get("amount_usd", 0)
        recipient = tool_input.get("recipient", "unknown")

        if amount > PAYMENT_THRESHOLD:
            print(f"  [PreToolUse Hook] BLOCKED ${amount} to '{recipient}' -> escalating to human")
            return {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Payment of ${amount:,.0f} to '{recipient}' exceeds the "
                    f"${PAYMENT_THRESHOLD:,.0f} automated approval limit. "
                    "This transaction requires human approval before proceeding."
                ),
            }

        print(f"  [PreToolUse Hook] ALLOWED ${amount} to '{recipient}' - within limit")

    return {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
    }


def build_agent_options_with_hooks() -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with both PostToolUse and PreToolUse hooks."""
    return ClaudeAgentOptions(
        allowed_tools=["search_web", "query_database", "fetch_api", "execute_payment"],
        hooks={
            # PostToolUse: normalize output from data retrieval tools
            "PostToolUse": [
                HookMatcher(
                    matcher="search_web|query_database|fetch_api",
                    hooks=[normalize_tool_output],
                )
            ],
            # PreToolUse: enforce payment policy before execution
            "PreToolUse": [
                HookMatcher(
                    matcher="execute_payment",
                    hooks=[policy_enforcement_hook],
                )
            ],
        },
        permission_mode="bypassPermissions",
        max_turns=5,
    )


def demo_hooks_normalization() -> None:
    """
    Demonstrate PostToolUse normalization by simulating hook calls directly.
    (In production, hooks fire automatically inside claude-agent-sdk query loop.)
    """
    print("\n=== Demo 1: PostToolUse Hook - Data Normalization ===\n")

    # Simulate raw outputs from different MCP tools
    mock_tool_outputs = [
        ("search_web",     {"items":  ["result A", "result B", "result C"]}),
        ("query_database", {"rows":   ["row 1", "row 2"]}),
        ("fetch_api",      {"data":   ["item X"]}),
        ("some_other_tool", {"output": "raw string"}),  # no normalization
    ]

    context = HookContext(signal=None)

    for tool_name, raw_output in mock_tool_outputs:
        hook_input: PostToolUseHookInput = {
            "hook_event_name": "PostToolUse",
            "tool_name": tool_name,
            "tool_input": {},
            "tool_response": raw_output,
            "tool_use_id": f"toolu_{tool_name[:4]}",
        }
        result = asyncio.get_event_loop().run_until_complete(
            normalize_tool_output(hook_input, None, context)
        )
        if result:
            print(f"  Normalized output: {json.dumps(result.get('updatedMCPToolOutput', {}))}")
        else:
            print(f"  Passed through unchanged: {raw_output}")
        print()


def demo_hooks_policy_enforcement() -> None:
    """
    Demonstrate PreToolUse policy enforcement by simulating hook calls directly.
    """
    print("\n=== Demo 2: PreToolUse Hook - Policy Enforcement ===\n")

    test_payments = [
        {"amount_usd": 500,    "recipient": "Vendor A"},    # should be allowed
        {"amount_usd": 9_999,  "recipient": "Vendor B"},    # should be allowed
        {"amount_usd": 10_001, "recipient": "Vendor C"},    # should be BLOCKED
        {"amount_usd": 25_000, "recipient": "Vendor D"},    # should be BLOCKED
    ]

    context = HookContext(signal=None)

    for payment in test_payments:
        hook_input: PreToolUseHookInput = {
            "hook_event_name": "PreToolUse",
            "tool_name": "execute_payment",
            "tool_input": payment,
        }
        result = asyncio.get_event_loop().run_until_complete(
            policy_enforcement_hook(hook_input, None, context)
        )
        decision = result.get("permissionDecision", "allow")
        reason   = result.get("permissionDecisionReason", "")
        status = "[OK] ALLOWED" if decision == "allow" else "[BLOCKED]"
        print(f"  {status}: ${payment['amount_usd']:,} -> {reason or 'within limit'}\n")


# ---------------------------------------------------------------------------
# Demo 3: Prompt Chaining
# ---------------------------------------------------------------------------

CHAIN_TOOLS = []  # no tools needed for this demo - pure text processing


def call_claude(prompt: str, system: str = "You are a helpful assistant.") -> str:
    """Single synchronous Claude call - building block for prompt chaining."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def prompt_chain_draft_critique_improve(topic: str) -> str:
    """
    Fixed 3-step prompt chain:
    Step 1: Generate initial draft
    Step 2: Critique the draft (identify weaknesses)
    Step 3: Improve based on critique

    Use when: steps are predetermined and don't depend on input content.
    """
    print(f"\n=== Demo 3: Prompt Chaining - '{topic}' ===\n")

    # Step 1: Draft
    print("  Step 1/3: Generating draft...")
    draft = call_claude(
        f"Write a concise 3-sentence summary about: {topic}",
        system="You are a technical writer. Be clear and precise.",
    )
    print(f"  Draft: {draft[:100]}...\n")

    # Step 2: Critique (uses draft as input)
    print("  Step 2/3: Critiquing draft...")
    critique = call_claude(
        f"Critique this summary. List 2-3 specific weaknesses:\n\n{draft}",
        system="You are a critical editor. Be specific and constructive.",
    )
    print(f"  Critique: {critique[:100]}...\n")

    # Step 3: Improve (uses both draft and critique)
    print("  Step 3/3: Improving based on critique...")
    improved = call_claude(
        f"""Improve this summary based on the critique below.

ORIGINAL SUMMARY:
{draft}

CRITIQUE:
{critique}

Write an improved version that addresses the critique.""",
        system="You are a technical writer. Incorporate all feedback.",
    )
    print(f"  Improved: {improved[:100]}...\n")
    print("  [OK] Prompt chain complete: 3 deterministic steps")

    return improved


# ---------------------------------------------------------------------------
# Demo 4: Dynamic Decomposition
# ---------------------------------------------------------------------------

COORDINATOR_SYSTEM = """You are a research coordinator.

Given a research topic, decompose it into 2-5 subtopics appropriate for that topic.
The number of subtopics should fit the topic - not always 3.

Return ONLY a JSON array of subtopic strings, nothing else.
Example: ["subtopic 1", "subtopic 2", "subtopic 3"]"""

SUBAGENT_SYSTEM = """You are a research specialist.
Write a 2-sentence summary of the given subtopic. Be factual and concise."""


def dynamic_decomposition(topic: str) -> dict[str, Any]:
    """
    Dynamic task decomposition:
    1. Coordinator analyzes topic and decides how many subtasks are appropriate
    2. Spawns one subagent per subtask (simulated with separate Claude calls)
    3. Aggregates results

    Use when: task structure depends on content, not fixed in advance.
    """
    print(f"\n=== Demo 4: Dynamic Decomposition - '{topic}' ===\n")

    # Step 1: Coordinator decides decomposition dynamically
    print("  [Coordinator] Analyzing topic and deciding decomposition...")
    raw = call_claude(
        f"Decompose this research topic into appropriate subtopics: {topic}",
        system=COORDINATOR_SYSTEM,
    )

    try:
        subtopics = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: extract lines if JSON parsing fails
        subtopics = [line.strip().strip('"') for line in raw.split("\n") if line.strip()]

    print(f"  [Coordinator] Decomposed into {len(subtopics)} subtopics (dynamic):")
    for i, st in enumerate(subtopics, 1):
        print(f"    -> Subtopic {i}: '{st}'")

    # Step 2: Spawn one subagent per subtopic (each with isolated context)
    print(f"\n  [Coordinator] Spawning {len(subtopics)} subagents...\n")
    findings: dict[str, str] = {}

    for subtopic in subtopics:
        # Each subagent gets only its own subtopic - no shared context
        result = call_claude(
            f"Topic: {subtopic}\nContext: Part of broader research on '{topic}'",
            system=SUBAGENT_SYSTEM,
        )
        findings[subtopic] = result
        print(f"  [Subagent] '{subtopic}': {result[:80]}...")

    # Step 3: Coordinator aggregates
    print(f"\n  [OK] Dynamic decomposition: {len(subtopics)} subagents completed")
    return {"topic": topic, "subtopics": subtopics, "findings": findings}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Demo 1: PostToolUse - data normalization
    demo_hooks_normalization()

    # Demo 2: PreToolUse - policy enforcement (blocking)
    demo_hooks_policy_enforcement()

    # Demo 3: Prompt chaining - fixed 3-step pipeline
    prompt_chain_draft_critique_improve("the impact of large language models on software engineering")

    # Demo 4: Dynamic decomposition - coordinator decides structure
    dynamic_decomposition("AI impact on healthcare")
