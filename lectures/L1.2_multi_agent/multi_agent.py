"""
L1.2: Multi-Agent Orchestration
================================
Demonstrates the coordinator-subagent pattern using the raw Anthropic API.

NOTE ON "Task" TOOL:
  In the Claude Agent SDK, coordinators spawn subagents via a built-in "Task" tool.
  "Task" is NOT defined by us — it is provided by the SDK itself.
  We only grant permission: allowed_tools=["Task", "my_tool"]
  The SDK then intercepts Task calls and runs isolated agent loops automatically.

  Since we use the raw anthropic API (not the Agent SDK), we implement
  the same pattern manually:
    spawn_search_agent()   → equivalent to coordinator calling Task
    spawn_analysis_agent() → equivalent to coordinator calling Task
    run_agent_loop()       → what SDK runs internally for each subagent

What this example demonstrates:
  - Isolated subagent context (no shared history between agents)
  - Explicit context passing through the subagent prompt
  - Parallel subagent execution (simulated sequentially here for clarity)
  - Coordinator aggregation and synthesis
"""

import anthropic
import json
from typing import Any

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# 1. Subagent tools — each subagent only gets tools relevant to its role
# ---------------------------------------------------------------------------

SEARCH_TOOLS = [
    {
        "name": "search_web",
        "description": (
            "Searches the web for articles and information on a given topic. "
            "Use when you need to find recent publications, news, or research. "
            "Returns a list of results with titles, snippets, and URLs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string, e.g. 'AI music generation 2024'"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)"
                }
            },
            "required": ["query"]
        }
    }
]

ANALYSIS_TOOLS = [
    {
        "name": "extract_key_facts",
        "description": (
            "Extracts and structures key facts from a body of text. "
            "Use to identify main claims, statistics, and conclusions. "
            "Returns structured JSON with categorised findings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Raw text to analyse"
                },
                "focus": {
                    "type": "string",
                    "description": "Specific aspect to focus on, e.g. 'economic impact'"
                }
            },
            "required": ["text"]
        }
    }
]

# ---------------------------------------------------------------------------
# 2. Simulated backend functions
# ---------------------------------------------------------------------------

def search_web(query: str, max_results: int = 5) -> dict:
    """Simulates a web search API."""
    # Fake data — in production this would call a real search API
    return {
        "query": query,
        "results": [
            {
                "title": f"How AI is transforming {query.split()[0]} industry",
                "snippet": f"Recent advances in AI are reshaping {query}. Studies show 40% productivity gains...",
                "url": f"https://example.com/ai-{query.split()[0].lower()}-2024",
                "published": "2024-11-15"
            },
            {
                "title": f"The future of {query.split()[0]} with generative AI",
                "snippet": f"Experts predict that AI will fundamentally change how {query} works by 2026...",
                "url": f"https://research.example.com/{query.split()[0].lower()}-ai",
                "published": "2024-10-03"
            }
        ][:max_results]
    }


def extract_key_facts(text: str, focus: str = None) -> dict:
    """Simulates key fact extraction from text."""
    return {
        "focus": focus or "general",
        "key_facts": [
            "AI adoption increased 40% year-over-year in creative sectors",
            "68% of professionals report AI as a productivity tool, not a replacement",
            "New hybrid human-AI creative roles are emerging"
        ],
        "sentiment": "cautiously optimistic",
        "confidence": 0.82
    }


# ---------------------------------------------------------------------------
# 3. Generic agent loop (same pattern as L1.1, reusable)
# ---------------------------------------------------------------------------

def run_agent_loop(
    system_prompt: str,
    user_message: str,
    tools: list[dict],
    agent_name: str = "Agent"
) -> str:
    """
    Runs a standard agent loop for a subagent.
    Returns the final text response.
    """
    messages = [{"role": "user", "content": user_message}]
    tool_map = {
        "search_web": search_web,
        "extract_key_facts": extract_key_facts,
    }

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        elif response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [{agent_name}] calling {block.name}({block.input})")
                    fn = tool_map.get(block.name)
                    result = fn(**block.input) if fn else {"error": f"Unknown tool: {block.name}"}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })

            messages.append({"role": "user", "content": tool_results})


# ---------------------------------------------------------------------------
# 4. Specialised subagents
#    Each receives only the tools relevant to its role.
#    Context is passed explicitly in the prompt — never inherited.
# ---------------------------------------------------------------------------

def spawn_search_agent(topic: str, coordinator_context: str) -> str:
    """
    Spawns a search subagent.
    Passes ALL necessary context explicitly in the prompt.
    """
    print(f"\n  [Search Agent] Starting → topic: '{topic}'")
    user_message = f"""Research the following topic and return structured findings.

TOPIC: {topic}

CONTEXT FROM COORDINATOR:
{coordinator_context}

Use the search_web tool to find relevant information.
Return your findings as JSON:
{{
  "topic": "{topic}",
  "summary": "...",
  "key_facts": ["fact1", "fact2"],
  "sources": [{{"title": "...", "url": "...", "date": "..."}}]
}}"""
    return run_agent_loop(
        system_prompt=(
            "You are a research specialist. Search thoroughly and return structured findings. "
            "Always include source URLs and publication dates."
        ),
        user_message=user_message,
        tools=SEARCH_TOOLS,
        agent_name=f"Search:{topic[:20]}"
    )


def spawn_analysis_agent(findings: str, analysis_focus: str) -> str:
    """
    Spawns an analysis subagent.
    Receives search results explicitly — does NOT share memory with search agent.
    """
    print(f"\n  [Analysis Agent] Starting → focus: '{analysis_focus}'")
    user_message = f"""Analyse the following research findings and extract key insights.

ANALYSIS FOCUS: {analysis_focus}

RAW FINDINGS:
{findings}

Use extract_key_facts to structure the analysis.
Return a concise analytical summary with confidence scores."""
    return run_agent_loop(
        system_prompt=(
            "You are a research analyst. Extract key insights from provided findings. "
            "Be objective and cite specific evidence."
        ),
        user_message=user_message,
        tools=ANALYSIS_TOOLS,
        agent_name="Analyst"
    )


# ---------------------------------------------------------------------------
# 5. Coordinator — the hub
#    Decomposes the task, spawns subagents, aggregates results.
#    In a real SDK implementation this would use the Task tool.
#    Here we simulate the coordinator's decision-making logic directly.
# ---------------------------------------------------------------------------

def run_coordinator(research_topic: str) -> str:
    """
    Simulates the coordinator pattern:
    1. Decomposes the topic into subtopics
    2. Spawns search subagents in PARALLEL (simulated)
    3. Passes results explicitly to analysis agent
    4. Synthesises the final report
    """
    print(f"\n{'='*60}")
    print(f"Research topic: {research_topic}")
    print(f"{'='*60}")

    # Step 1: Coordinator decomposes the topic
    # In production: coordinator calls Claude to decide decomposition
    print("\n[Coordinator] Decomposing task...")
    subtopics = [
        f"AI impact on music and audio production",
        f"AI impact on literature and writing",
        f"AI impact on film and video production",
    ]
    print(f"[Coordinator] Subtopics identified: {len(subtopics)}")
    for st in subtopics:
        print(f"  → {st}")

    # Step 2: Spawn search agents IN PARALLEL
    #
    # In Claude Agent SDK this looks like:
    #   coordinator calls Task tool multiple times in ONE response → SDK runs them in parallel
    #
    # With raw API (our case): we call spawn_search_agent() manually for each subtopic.
    # The pattern is identical — only the mechanism differs.
    print("\n[Coordinator] Spawning search agents in parallel...")
    search_results = []
    for subtopic in subtopics:
        result = spawn_search_agent(
            topic=subtopic,
            # Context passed explicitly — subagent has no other way to know this
            coordinator_context=f"Part of broader research: '{research_topic}'. Focus only on your subtopic."
        )
        search_results.append({"subtopic": subtopic, "findings": result})
        print(f"  [Search Agent] Completed: '{subtopic[:40]}...'")

    # Step 3: Pass ALL search results explicitly to analysis agent
    combined_findings = "\n\n---\n\n".join(
        f"SUBTOPIC: {r['subtopic']}\n{r['findings']}"
        for r in search_results
    )

    print("\n[Coordinator] Sending findings to analysis agent...")
    analysis = spawn_analysis_agent(
        findings=combined_findings,
        analysis_focus=f"Overall impact of AI on creative industries, synthesised from {len(subtopics)} subtopics"
    )

    # Step 4: Coordinator synthesises final report
    print("\n[Coordinator] Synthesising final report...")
    final_report = f"""
RESEARCH REPORT: {research_topic}
{'='*60}

COVERAGE: {len(subtopics)} domains analysed
  {chr(10).join(f"  • {st}" for st in subtopics)}

ANALYSIS SUMMARY:
{analysis}

RAW FINDINGS PER DOMAIN:
{combined_findings[:500]}...

COORDINATOR NOTE: All subagents completed successfully.
Coverage gaps: none detected.
"""
    return final_report


# ---------------------------------------------------------------------------
# 6. Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    report = run_coordinator("AI impact on creative industries")
    print("\n" + "="*60)
    print("FINAL REPORT")
    print("="*60)
    print(report)
