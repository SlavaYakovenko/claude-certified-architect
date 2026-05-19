# L1.3 - Hooks and Task Decomposition

**Domain:** 1 - Agentic Architecture and Orchestration (27% of the exam)
**Tasks:** 1.3, 1.4 - Multi-stage Workflows, Session Management

---

## Why This Matters

Hooks allow intercepting and modifying agent behavior without changing the main loop - normalizing data from MCP tools and blocking policy violations before Claude executes them. Task decomposition determines how to break down a complex task: prompt chaining for predictable steps, dynamic decomposition for open-ended research.

---

## Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │               Agent Loop                    │
                    │                                             │
User ──->           │  Claude decides to call a tool              │
                    │         │                                   │
                    │         v                                   │
                    │  ┌─────────────────┐                        │
                    │  │  PreToolUse     │ <- HOOKS (before call) │
                    │  │  Hook           │   permissionDecision:  │
                    │  │  allow/deny/ask │   "deny" -> block      │
                    │  └────────┬────────┘                        │
                    │           │ allow                           │
                    │           v                                 │
                    │    Tool is executed                         │
                    │           │                                 │
                    │           v                                 │
                    │  ┌─────────────────┐                        │
                    │  │  PostToolUse    │ <- HOOKS (after call)  │
                    │  │  Hook           │   updatedMCPToolOutput:│
                    │  │  normalization  │   normalized format    │
                    │  └────────┬────────┘                        │
                    │           │                                 │
                    │           v                                 │
                    │    Claude receives the result               │
                    └─────────────────────────────────────────────┘

DECOMPOSITION:

Prompt Chaining (predictable tasks):        Dynamic Decomposition (open tasks):
  Step 1 -> Step 2 -> Step 3 -> Result         Coordinator analyzes the task
  Fixed sequence                            Dynamically decides: 2 or 5 subtasks
  Example: draft -> critique -> improve       Example: topic research
```

---

## Key Concepts

### 1. Hooks - Interception Points of the Agent Loop

A **hook** is a Python function called by the SDK at a specific point in the loop. It is registered in `ClaudeAgentOptions(hooks=...)`.

| Hook Type | When it Fires | What Can Be Done |
|---|---|---|
| `PreToolUse` | Before tool execution | Allow, block, modify input |
| `PostToolUse` | After tool execution | Normalize output, add context |
| `PostToolUseFailure` | After tool error | Log, structure the error |
| `SubagentStart` | At subagent launch (Task) | Log, configure isolation |
| `SubagentStop` | At subagent completion | Log the result |
| `Stop` | At agent completion | Final actions, notifications |

### 2. PostToolUse Hook - Data Format Normalization

Different MCP tools return data in different formats. A `PostToolUse` hook normalizes them to a single format **before** Claude receives the result.

```python
async def normalize_tool_output(
    hook_input: PostToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> HookJSONOutput:
    """Normalize MCP tool outputs to a consistent format."""
    tool_name = hook_input["tool_name"]
    raw_output = hook_input["tool_response"]

    # Each MCP tool returns data differently - normalize here
    if tool_name == "search_web":
        normalized = {"results": raw_output.get("items", []), "source": "web"}
    elif tool_name == "query_database":
        normalized = {"results": raw_output.get("rows", []), "source": "db"}
    elif tool_name == "fetch_api":
        normalized = {"results": raw_output.get("data", []), "source": "api"}
    else:
        return {}  # no normalization needed - return empty dict

    return {
        "hookEventName": "PostToolUse",
        "updatedMCPToolOutput": normalized,  # Claude sees this instead of raw_output
    }
```

Key field: `updatedMCPToolOutput` - if returned, Claude receives exactly this instead of the original tool response.

### 3. PreToolUse Hook - Interception and Blocking

A `PreToolUse` hook can **block a tool call** before its execution via `permissionDecision: "deny"`.

```python
async def policy_enforcement_hook(
    hook_input: PreToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> HookJSONOutput:
    """Block tool calls that violate business policy."""
    tool_name = hook_input["tool_name"]
    tool_input = hook_input["tool_input"]

    # Block financial operations above threshold
    if tool_name == "execute_payment":
        amount = tool_input.get("amount_usd", 0)
        if amount > 10_000:
            return {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",  # tool is NOT called
                "permissionDecisionReason": (
                    f"Payment ${amount} exceeds $10,000 limit. "
                    "Escalating to human approval."
                ),
            }

    return {"hookEventName": "PreToolUse", "permissionDecision": "allow"}
```

| `permissionDecision` | What Happens |
|---|---|
| `"allow"` | Tool is executed (default) |
| `"deny"` | Tool is NOT called, Claude receives a refusal message |
| `"ask"` | Interactive request to the user (only in interactive mode) |

### 4. Hook Registration in the SDK

```python
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

options = ClaudeAgentOptions(
    allowed_tools=["search_web", "query_database", "execute_payment"],
    hooks={
        "PostToolUse": [
            HookMatcher(
                matcher="search_web|query_database|fetch_api",  # tool names, pipe-separated
                hooks=[normalize_tool_output],
            )
        ],
        "PreToolUse": [
            HookMatcher(
                matcher="execute_payment",  # only intercept payment tool
                hooks=[policy_enforcement_hook],
            )
        ],
    }
)
```

`matcher` - a filter by tool name (pipe-separated string). `None` means "all tools".

### 5. Prompt Chaining - for Predictable Tasks

**Prompt chaining** is a sequence of fixed steps where the output of one step is the input for the next.

```
Input
 │
 v
[Step 1: Draft]          Claude creates a draft
 │
 v
[Step 2: Critique]       Claude critiques the draft
 │
 v
[Step 3: Improvement]    Claude improves based on critique
 │
 v
Final Result
```

When to use:
- The task can be broken down into a predictable number of steps
- Each step has a clear input and output format
- No adaptation to the task content is needed

```python
def prompt_chain(text: str) -> str:
    """Fixed 3-step chain: draft -> critique -> improve."""
    draft = call_claude(f"Write a summary of: {text}")
    critique = call_claude(f"Critique this summary:\n{draft}")
    improved = call_claude(f"Improve the summary based on this critique:\n{critique}\n\nOriginal:\n{draft}")
    return improved
```

### 6. Dynamic Decomposition - for Open-Ended Tasks

**Dynamic decomposition** - the coordinator itself decides how many parts to break the task into and how.

```
Task: "Research AI impact on the labor market"
 │
 v
Coordinator analyzes the task
 │
 ├─-> Determines 4 subtopics (not 3, not 5 - depending on the topic)
 │
 ├─-> Subagent 1: "AI in manufacturing"
 ├─-> Subagent 2: "AI in services"
 ├─-> Subagent 3: "New professions"
 └─-> Subagent 4: "Employment statistics"
```

When to use:
- The task is open-ended, its scope is unpredictable
- Decomposition depends on the content, not just the task type
- Adaptation to the specific request is needed

### 7. Session Management: `--resume` and `fork_session`

| Mechanism | Where it Works | Purpose |
|---|---|---|
| `--resume <session-name>` | Claude Code CLI | Resume an interrupted session from the same point |
| `fork_session=True` | `ClaudeAgentOptions` in SDK | Create a session copy for a parallel branch |
| `continue_conversation=True` | `ClaudeAgentOptions` | Continue the last session without a name |

```python
# fork_session: run parallel branches from the same checkpoint
options_branch_a = ClaudeAgentOptions(fork_session=True, ...)
options_branch_b = ClaudeAgentOptions(fork_session=True, ...)
# Both branches start from the same session state - isolated from each other
```

---

## Anti-patterns

### [x] Normalization Inside Prompt Instead of Hook

```python
# BAD: asking Claude itself to normalize data
system_prompt = """
When you get results from search_web, convert 'items' field to 'results'.
When you get results from query_database, convert 'rows' field to 'results'.
"""
```
Why it's bad: probabilistic compliance - Claude may not normalize or normalize incorrectly. A PostToolUse hook is a deterministic guarantee.

### [x] Blocking via Prompt Instead of PreToolUse Hook

```python
# BAD: relying on a prompt instruction for financial protection
system_prompt = "Never execute payments above $10,000."
```
Why it's bad: prompt instructions are probabilistic controls. Critical business constraints require a programmatic PreToolUse hook with `permissionDecision: "deny"`.

### [x] Prompt Chaining Where Dynamic Decomposition is Needed

```python
# BAD: fixed 3 steps for an open-ended research task
subtopics = ["economic impact", "social impact", "future outlook"]  # always 3, always these
```
Why it's bad: the topic "AI in medicine" requires different subtopics than "AI in education". Fixed decomposition = incomplete coverage.

---

## Complete Working Example

File: [hooks_decomposition.py](hooks_decomposition.py)

### Example Structure

```
1. PostToolUse hook      - normalization of different MCP tool formats
2. PreToolUse hook       - blocking payments above the threshold
3. Hook registration     - ClaudeAgentOptions with hooks dict
4. Prompt chaining       - 3-step pipeline: draft -> critique -> improve
5. Dynamic decomposition - coordinator with Task and dynamic number of subtasks
6. Demonstration         - running all patterns with output
```

### Key Fragment - PostToolUse Normalization

```python
async def normalize_tool_output(
    hook_input: PostToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> HookJSONOutput:
    """Normalize MCP tool output formats to a unified structure."""
    tool_name = hook_input["tool_name"]
    raw = hook_input["tool_response"]

    FORMAT_MAP = {
        "search_web":     lambda r: {"results": r.get("items", []),   "source": "web"},
        "query_database": lambda r: {"results": r.get("rows", []),     "source": "db"},
        "fetch_api":      lambda r: {"results": r.get("data", []),     "source": "api"},
    }

    if tool_name not in FORMAT_MAP:
        return {}  # pass through - no normalization

    return {
        "hookEventName": "PostToolUse",
        "updatedMCPToolOutput": FORMAT_MAP[tool_name](raw),
    }
```

### Key Fragment - PreToolUse Blocking

```python
async def policy_enforcement_hook(
    hook_input: PreToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> HookJSONOutput:
    """Enforce payment policy: block transactions above threshold."""
    if hook_input["tool_name"] == "execute_payment":
        amount = hook_input["tool_input"].get("amount_usd", 0)
        if amount > PAYMENT_THRESHOLD:
            print(f"[Hook] BLOCKED payment of ${amount} -> escalating to human")
            return {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Payment ${amount} exceeds policy limit ${PAYMENT_THRESHOLD}. "
                    "Human approval required."
                ),
            }
    return {"hookEventName": "PreToolUse", "permissionDecision": "allow"}
```

---

## How to Run

```bash
cd studies/cca
source .venv/bin/activate
export ANTHROPIC_API_KEY=sk-ant-...
python3 lectures/L1.3_hooks_decomposition/hooks_decomposition.py
```

### Expected Output

```
=== Demo 1: PostToolUse Hook - Data Normalization ===
[Hook] PostToolUse fired for: search_web
[Hook] Normalizing 'items' -> 'results', source=web
[Hook] PostToolUse fired for: query_database
[Hook] Normalizing 'rows' -> 'results', source=db
[OK] All tools normalized to: {"results": [...], "source": "..."}

=== Demo 2: PreToolUse Hook - Policy Enforcement ===
[Hook] PreToolUse fired for: execute_payment (amount=$500)
[Hook] ALLOWED - within $10,000 limit
[Hook] PreToolUse fired for: execute_payment (amount=$25,000)
[Hook] BLOCKED payment of $25,000 -> escalating to human
[OK] Large payment correctly blocked

=== Demo 3: Prompt Chaining ===
Step 1/3: Generating draft...
Step 2/3: Critiquing draft...
Step 3/3: Improving based on critique...
[OK] Chain complete: 3 steps, deterministic flow

=== Demo 4: Dynamic Decomposition ===
[Coordinator] Analyzing task: "AI impact on healthcare"
[Coordinator] Decomposed into 4 subtopics (dynamic):
  -> Subtopic 1: "AI in diagnostics"
  -> Subtopic 2: "AI in drug discovery"
  -> Subtopic 3: "AI in patient care"
  -> Subtopic 4: "Regulatory and ethical challenges"
[OK] Dynamic decomposition: 4 subagents spawned
```

---

## Self-Check Questions

1. A system blocks financial operations via an instruction in the system prompt. Is this reliable? *(No - prompt instructions are probabilistic. For financial constraints, a PreToolUse hook with `permissionDecision: "deny"` is needed - a programmatic guarantee)*

2. Three MCP tools return data in different formats. Where is the best place to normalize them to a single format? *(In a PostToolUse hook via `updatedMCPToolOutput` - deterministically, before Claude receives the result)*

3. Task: "Write a report on topic X: first a draft, then a critique, then a final version." Which decomposition should be used? *(Prompt chaining - the number of steps and their type are fixed and do not depend on the content of X)*

4. Task: "Research topic X." Which decomposition should be used? *(Dynamic - the coordinator analyzes the topic and decides itself how many subtasks are needed and which ones)*

5. What happens if a PreToolUse hook returns `permissionDecision: "deny"`? *(The tool will NOT be called. Claude will receive a refusal message with `permissionDecisionReason` and continue the loop with this information)*

---

## Connection to the Exam

**Typical question:** An agent processes data from three MCP sources. Each returns a result field with a different name (`items`, `rows`, `data`). Claude sometimes gets confused by the formats. Best solution?

- [x] Add an instruction to the system prompt: "when you see `items`, use it as `results`" - *probabilistic control, Claude might ignore it*
- [x] Ask Claude to normalize itself before analysis - *another agentic step, consumes context, no guarantee*
- [OK] Add a PostToolUse hook that normalizes `updatedMCPToolOutput` to a single format - *deterministic, transparent, before Claude sees the data*

**Principle:** if deterministic data transformation is needed - use a hook; if probabilistic processing - use a prompt.

---

**Typical question 2:** When to use prompt chaining vs dynamic decomposition?

- [OK] Prompt chaining -> the number of steps is known in advance, steps are the same for any input.
- [OK] Dynamic decomposition -> the task structure depends on the content, adaptation is needed.

---

*Next step: L2.1 - Tool Design*
