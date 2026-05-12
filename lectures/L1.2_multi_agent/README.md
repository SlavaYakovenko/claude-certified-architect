# L1.2 — Multi-Agent Orchestration

**Domain:** 1 — Agentic Architecture and Orchestration (27% of the exam)
**Tasks:** 1.2, 1.3, 1.4 — Orchestration, Context Transfer, Multi-stage Workflows

---

## Why This Matters

A single agent has limited context and cannot effectively perform multiple complex tasks simultaneously. A multi-agent architecture allows breaking down a task into specialized performers and running them in parallel — with a coordinator managing the entire process.

---

## Diagram

```
User
    │
    ▼
┌─────────────────────────────────────────┐
│           COORDINATOR                   │
│  - task decomposition                   │
│  - delegation to subagents              │
│  - results aggregation                  │
│  - error handling                       │
└──────┬──────────────┬────────────────┬──┘
       │              │                │
       ▼              ▼                ▼
 ┌──────────┐   ┌──────────┐   ┌──────────┐
 │ Agent 1  │   │ Agent 2  │   │ Agent 3  │
 │ (search) │   │(analysis)│   │(synthesis)│
 └──────────┘   └──────────┘   └──────────┘
       │              │                │
       └──────────────┴────────────────┘
                      │
                      ▼
                Final Report
```

The pattern is called **"Hub and Spoke"**: the coordinator is the hub, and the subagents are the spokes.

---

## Key Concepts

### 1. The `Task` Tool — A Mechanism for Spawning Subagents

#### Three Levels: Anthropic API, Claude Agent SDK, Claude Code

| | Anthropic API | Claude Agent SDK | Claude Code CLI |
|---|---|---|---|
| What it is | HTTP client | Python wrapper over Claude Code CLI | Anthropic's agentic system |
| Package | `anthropic` | `claude-agent-sdk` (pip) | `claude` binary |
| Tools | Defined by us | `allowed_tools=["Task"]` + ours | `Task` is built-in |
| Parallelism | Manual (asyncio) | Automatic | Automatic |

**Key Fact:** `claude-agent-sdk` is a Python package (`pip install claude-agent-sdk`) that runs the Claude Code CLI **as a subprocess** and provides an async interface. `Task` is a built-in tool of Claude Code, not a tool that we write.

```python
# claude-agent-sdk — real working code
import asyncio
import claude_agent_sdk
from claude_agent_sdk import ClaudeAgentOptions

async def run_coordinator():
    options = ClaudeAgentOptions(
        allowed_tools=["Task"],  # Task is built-in, we just enable it
        system_prompt="You are a research coordinator. Use Task to spawn subagents.",
    )
    async for msg in claude_agent_sdk.query(
        prompt="Research AI impact on creative industries. Spawn separate subagents for music, film, and literature.",
        options=options,
    ):
        print(msg)

asyncio.run(run_coordinator())
```

When Claude decides to call `Task`, the SDK **automatically**:
1. Intercepts the call
2. Starts a new agent loop (subagent) with isolated context
3. Returns the result to the coordinator

```
Claude (coordinator) calls:
  tool_use: Task → { "description": "Search AI trends", "prompt": "..." }
                        ↓
              SDK intercepts the call
                        ↓
         Starts a new agent loop
         with isolated context
                        ↓
         Returns the result to the coordinator
```

#### How this looks in our code (at the raw API level)

The file `multi_agent.py` uses the `anthropic` API directly — `Task` is not there. We **manually implement** what the SDK does automatically: the functions `spawn_search_agent()` and `spawn_analysis_agent()` are our manual implementation of the `Task` pattern.

```
claude-agent-sdk (automatically):   Our multi_agent.py (manually):
──────────────────────────────       ─────────────────────────────
coordinator calls Task            →  coordinator calls spawn_search_agent()
SDK starts subagent               →  spawn_search_agent() calls run_agent_loop()
SDK returns tool_result           →  function returns a string with the result
SDK runs in parallel              →  sequential for-loop
```

On the exam, `Task` is described as a tool available through `claude-agent-sdk` or directly in Claude Code — **not** as a tool that we write in the `input_schema` ourselves.

> **Critical Distinction:**
> - `claude-agent-sdk` → `allowed_tools=["Task"]` → **sufficient**, Claude automatically spawns isolated subagents.
> - Raw `anthropic` API → adding `"Task"` to the tool list → **DOES NOT work**, the API will treat it as a regular user tool and wait for our implementation. There is no automation.

### 2. Isolated Context of Subagents

A subagent **does not inherit** the coordinator's history. It starts with a clean slate and only sees what we explicitly pass in its prompt.

| What the subagent sees | What it DOES NOT see |
|---|---|
| Prompt passed by the coordinator | Coordinator's dialogue history |
| Tools assigned to it | Tools of other agents |
| Results of its own calls | Results of other subagents |

### 3. Context Transfer — Only Explicitly via Prompt

```python
# BAD: subagent will not see the coordinator's context
task_result = task_tool.run("Analyze the documents")

# GOOD: pass everything necessary directly in the prompt
task_result = task_tool.run(f"""
Analyze the following documents for key findings:

DOCUMENTS:
{documents_content}

FOCUS AREAS: {focus_areas}
OUTPUT FORMAT: structured JSON with fields: summary, key_facts, sources
""")
```

### 4. Parallel Launch of Subagents

The coordinator can launch several subagents **in a single response** — they are executed in parallel:

```
Coordinator returns:
  tool_use: Task → "Search for AI trends in healthcare"
  tool_use: Task → "Search for AI trends in finance"
  tool_use: Task → "Search for AI trends in education"

All three subagents are launched simultaneously.
```

### 5. Role of the Coordinator

The coordinator **does not execute** tasks — it manages:

| Function | Description |
|---|---|
| Decomposition | Breaks a large task into subtasks |
| Delegation | Selects a subagent for each subtask |
| Aggregation | Collects results and synthesizes the conclusion |
| Error Handling | Reacts to subagent failures |
| Iterative Refinement | In case of gaps — re-delegates |

---

## Anti-patterns

### ❌ Too Narrow Task Decomposition

```python
# Topic: "AI impact on creative industries"
# BAD — coordinator decomposed only visual subtopics:
subtasks = [
    "AI in digital art creation",
    "AI in graphic design",
    "AI in photography"
]
# Result: music, literature, film — not covered at all
```

Why it's bad: subagents work correctly, but the outcome is incomplete — an error in decomposition, not in execution.

### ❌ Expecting Automatic Context Inheritance

```python
# BAD: expecting subagent to "know" previous results
task_tool.run("Now analyze the documents we found earlier")
# The subagent hasn't seen "earlier" — it has no coordinator history
```

Why it's bad: the subagent starts with an empty context, "earlier" does not exist for it.

### ❌ Direct Communication Between Subagents

```python
# BAD: agent A passes the result directly to agent B
agent_b.run(agent_a_result)
```

Why it's bad: observability is lost, error handling becomes unpredictable. **All communication goes through the coordinator.**

---

## Complete Working Example

Two files — one pattern, two levels:

| File | Level | What it demonstrates |
|---|---|---|
| [multi_agent.py](multi_agent.py) | Raw `anthropic` API | Manual implementation of the Task pattern |
| [multi_agent_sdk.py](multi_agent_sdk.py) | `claude-agent-sdk` | Task as a built-in SDK tool |

File: [multi_agent.py](multi_agent.py)

### Example Structure

```
1. Subagent tools      — search_web(), analyze_document()
2. Search subagent     — searches for information on the topic
3. Analyst subagent    — analyzes the found data
4. Coordinator         — decomposes, delegates in parallel, synthesizes
5. Demonstration       — topic research with a final report
```

### Key Fragment — Parallel Launch of Subagents

```python
# Coordinator launches several Tasks in one response:
coordinator_response = client.messages.create(
    model="claude-opus-4-6",
    system=COORDINATOR_SYSTEM_PROMPT,
    tools=COORDINATOR_TOOLS,  # includes "Task"
    messages=messages
)

# If Claude returned several tool_use with Task — they are parallel:
# block[0]: Task → "Search healthcare AI trends"
# block[1]: Task → "Search finance AI trends"
# Execute both → collect both results → send to coordinator
```

### Key Fragment — Explicit Context Transfer to Subagent

```python
def spawn_search_agent(topic: str, context: str) -> str:
    """Spawns a search subagent with explicit context in the prompt."""
    response = client.messages.create(
        model="claude-opus-4-6",
        system="You are a research specialist. Search thoroughly and return structured findings.",
        tools=SEARCH_TOOLS,   # only search tools, not everything
        messages=[{
            "role": "user",
            "content": f"""Research the following topic:

TOPIC: {topic}

CONTEXT FROM COORDINATOR:
{context}

Return findings as JSON: {{"summary": "...", "key_facts": [...], "sources": [...]}}"""
        }]
    )
    # Inside — a regular agent loop (L1.1)
    return run_agent_loop(response, SEARCH_TOOLS)
```

---

## How to Run

```bash
cd studies/cca
source .venv/bin/activate
export ANTHROPIC_API_KEY=sk-ant-...
python3 lectures/L1.2_multi_agent/multi_agent.py
```

### Expected Output

```
============================================================
Research Topic: AI impact on creative industries
============================================================

[Coordinator] Decomposing task...
[Coordinator] Launching 3 subagents in parallel:
  → Agent 1: "AI in music and audio production"
  → Agent 2: "AI in literature and writing"
  → Agent 3: "AI in film and video production"

[Agent 1] Iteration 1: tool_use → search_web(...)
[Agent 2] Iteration 1: tool_use → search_web(...)
[Agent 3] Iteration 1: tool_use → search_web(...)

[Agent 1] Completed. Found: 5 sources.
[Agent 2] Completed. Found: 4 sources.
[Agent 3] Completed. Found: 6 sources.

[Coordinator] Synthesizing results...

✅ Final report ready (847 words, 15 sources)
```

---

## Self-Check Questions

1. The coordinator launched 3 subagents. One returned an error. What should the coordinator do? *(Continue with partial results from the two successful agents, annotate the gap in the report — do not terminate the entire process)*

2. Why doesn't the synthesis subagent see the results of the search subagent automatically? *(Isolated context — the coordinator must explicitly pass search results in the synthesis prompt)*

3. Topic "AI in creative industries" → coordinator decomposed only into visual subtopics. Subagents worked correctly. What is the error? *(Error in coordinator's decomposition, not in subagents — they executed what they were assigned)*

4. Why must `"Task"` be in the coordinator's `allowedTools`? *(Without it, the coordinator cannot call the Task tool to spawn subagents — the call will be blocked)*

---

## Connection to the Exam

**Typical question:** A research system covers only visual art, skipping music and literature. Each subagent works correctly. Root cause?

- ❌ Synthesis agent lacks instructions for identifying gaps — *subagents performed tasks correctly*
- ❌ Search agent makes insufficiently broad queries — *it searches exactly what it was assigned*
- ✅ Coordinator decomposed the topic too narrowly — *coordinator logs point directly to the cause*

**Principle:** if subagents work correctly but the result is incomplete — look at the coordinator's decomposition.

---

*Next step: L1.3 — Hooks and Task Decomposition*

---

## Appendix: What `claude-agent-sdk` does when it sees a Task call

`claude-agent-sdk` is a real Python package (`pip install claude-agent-sdk`) that wraps the Claude Code CLI. When the coordinator calls `Task`, the SDK performs the following sequence of steps **automatically and invisibly to us**:

### Full Sequence Inside the SDK

```
1. Coordinator returns a response with tool_use:
   ┌─────────────────────────────────────────────┐
   │ stop_reason: "tool_use"                     │
   │ content: [                                  │
   │   {                                         │
   │     type: "tool_use",                       │
   │     id:   "toolu_AAA",                      │
   │     name: "Task",                           │
   │     input: {                                │
   │       "description": "Search AI in music",  │
   │       "prompt": "Research AI trends in...", │
   │       "allowed_tools": ["search_web"],      │
   │       "system_prompt": "You are a search.." │
   │     }                                       │
   │   }                                         │
   │ ]                                           │
   └─────────────────────────────────────────────┘
                        │
                        ▼
2. SDK intercepts the Task call (does not pass it to our code)
   SDK creates a new isolated context:
   ┌─────────────────────────────────────┐
   │ messages = []          ← empty history
   │ system   = input["system_prompt"]   │
   │ tools    = input["allowed_tools"]   │
   │ first user message = input["prompt"]│
   └─────────────────────────────────────┘
                        │
                        ▼
3. SDK starts a standard agent loop (L1.1) for the subagent:
   ┌────────────────────────────────────────────────────┐
   │  while True:                                       │
   │    response = client.messages.create(              │
   │        system=subagent_system,                     │
   │        tools=subagent_tools,   ← only its tools    │
   │        messages=subagent_messages                  │
   │    )                                               │
   │    if stop_reason == "end_turn": break             │
   │    if stop_reason == "tool_use": execute & append  │
   └────────────────────────────────────────────────────┘
                        │
                        ▼
4. Subagent completes (end_turn)
   SDK takes the subagent's final text
   and wraps it in a tool_result for the coordinator:
   ┌─────────────────────────────────────────────┐
   │ {                                           │
   │   type: "tool_result",                      │
   │   tool_use_id: "toolu_AAA",  ← same ID     │
   │   content: "<subagent's final answer>"      │
   │ }                                           │
   └─────────────────────────────────────────────┘
                        │
                        ▼
5. SDK adds tool_result to the coordinator's history
   and continues its agent loop
```

### Parallel Launch — What Happens Inside the SDK

If the coordinator returned **two** `Task` calls in one response:

```
Coordinator: [Task("Search music"), Task("Search film")]
                    │                      │
                    ▼                      ▼
           SDK launches both     ←─── in parallel (asyncio / threads)
                    │                      │
             Agent 1 loop           Agent 2 loop
             (isolated)             (isolated)
                    │                      │
                    └──────────┬───────────┘
                               ▼
                  SDK collects both tool_results
                  Adds them to the coordinator's history
                  Continues the coordinator's loop
```

### Key Isolation Properties

| What is isolated | Why |
|---|---|
| Message history | Each subagent starts with `messages = []` |
| System prompt | Taken from the `Task` parameter, not from the coordinator |
| Tool set | Only those passed in the task's `allowed_tools` |
| Memory state | Subagents do not share memory between calls |

### Summary: What we implement manually in our code

```
SDK does automatically:          Our code does manually:
──────────────────────────       ──────────────────────────
Intercept Task call           →  call spawn_search_agent()
Create isolated context       →  new messages=[] inside
                                 spawn_*_agent()
Start agent loop              →  run_agent_loop()
Pack result into tool_result  →  function returns a string,
                                 coordinator uses it itself
Parallel launch               →  sequential for-loop
                                 (in real SDK — asyncio)
```
