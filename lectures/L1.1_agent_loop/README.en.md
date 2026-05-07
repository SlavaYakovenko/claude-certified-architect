# L1.1 — Agent Loop

**Domain:** 1 — Agentic Architecture and Orchestration (27% of the exam)
**Task:** 1.1 — Designing and implementing agent loops for autonomous task execution

---

## What is an Agent?

A standard Claude call is request-response. One round.

An **Agent** is a loop in which Claude itself decides:
- which tool to call
- whether the next call is needed
- when the task is complete

---

## Agent Loop Diagram

```
User: "Find the weather in London and convert to Fahrenheit"
                        │
                        ▼
          ┌─────────────────────────┐
          │  client.messages.create │  ← send request with tools
          └─────────────────────────┘
                        │
                        ▼
              Check stop_reason
                        │
           ┌────────────┴────────────┐
           │                         │
    "tool_use"                  "end_turn"
           │                         │
           ▼                         ▼
   Execute tools              Return response ✅
   Add to history
           │
           └──────────────────────────┐
                                      ▼
                         client.messages.create (again)
```

---

## Key Concepts

### 1. `stop_reason` — the only reliable completion signal

| Value | Action |
|----------|------------|
| `"tool_use"` | Execute tools → add results → repeat |
| `"end_turn"` | Extract text → return response to user |
| `"max_tokens"` | Handle as an error (response truncated) |

### 2. Conversation history accumulates between iterations

```
Iteration 1:
  messages = [{"role": "user", "content": "...request..."}]
  → Claude responds: tool_use(get_weather)

Iteration 2:
  messages = [
    {"role": "user",      "content": "...request..."},
    {"role": "assistant", "content": [tool_use block]},   ← added
    {"role": "user",      "content": [tool_result block]} ← added
  ]
  → Claude sees the result and decides: call calculate
```

It is this history that allows Claude to reason: "I already found the temperature is 12°C, now I'll calculate the formula."

### 3. `tool_use_id` — the link between request and result

Each tool call has a unique `id`. The result must be returned with the same `id`:

```python
# Claude requests:
{
    "type": "tool_use",
    "id": "toolu_01abc",      # ← this ID
    "name": "get_weather",
    "input": {"city": "London"}
}

# We respond:
{
    "type": "tool_result",
    "tool_use_id": "toolu_01abc",  # ← same ID
    "content": '{"temp": 12, "condition": "rain"}'
}
```

---

## Anti-patterns — What NOT to do

### ❌ Parsing response text to determine completion
```python
# BAD
if "done" in response.content[0].text.lower():
    break
```
Why it's bad: fragile, non-deterministic, doesn't work with other response languages.

### ❌ Iteration limit as the primary stopping mechanism
```python
# BAD
for i in range(10):  # "no more than 10 iterations"
    ...
```
Why it's bad: the agent terminates based on a timer, not task logic. Interrupts valid long chains.

> **Acceptable** to have an iteration limit as protection against infinite loops — but not as the primary mechanism. The primary mechanism is `stop_reason = "end_turn"`.

### ❌ Checking text as a completion indicator
```python
# BAD
if response.stop_reason == "end_turn" and "DONE" in text:
    break
```
This is redundant: `end_turn` already signifies completion.

---

## Full Working Example

File: [agent_loop.py](agent_loop.py)

### Example Structure

```
1. Backend functions    — get_weather(), calculate()
2. Tool descriptions (TOOLS) — critical for tool selection
3. Dispatcher         — execute_tool() calls the correct function
4. Agent loop        — run_agent() — the main pattern
5. Three example requests
```

### Key Fragment — The Loop

```python
while True:
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        tools=TOOLS,
        messages=messages          # ← pass the entire history
    )

    if response.stop_reason == "end_turn":
        return final_text          # ✅ EXIT

    elif response.stop_reason == "tool_use":
        # 3a. Save assistant's response to history
        messages.append({"role": "assistant", "content": response.content})

        # 3b. Execute tools
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,   # ← link ID
                    "content": result
                })

        # 3c. Add results to history
        messages.append({"role": "user", "content": tool_results})
        # → continue while True
```

---

## How to Run

```bash
cd studies/cca
source .venv/bin/activate
export ANTHROPIC_API_KEY=sk-ant-...
python3 lectures/L1.1_agent_loop/agent_loop.py
```

### Expected Output — Example 1 ("What's the weather in Kyiv?")

```
============================================================
Request: What's the weather in Kyiv?
============================================================

--- Iteration 1 ---
stop_reason: tool_use
  📞 Claude calls: get_weather
  ⚙️  Executing tool: get_weather({'city': 'Kyiv'})

--- Iteration 2 ---
stop_reason: end_turn

✅ Final answer: In Kyiv it is currently -5°C and snowing.
```

### Expected Output — Example 3 (chain)

```
--- Iteration 1 ---
stop_reason: tool_use
  📞 Claude calls: get_weather   ← first finds out the temperature

--- Iteration 2 ---
stop_reason: tool_use
  📞 Claude calls: calculate     ← then calculates using the formula

--- Iteration 3 ---
stop_reason: end_turn

✅ Final answer: In London it is 12°C, which corresponds to 53.6°F.
```

> Important: Claude builds the chain itself. We didn't explicitly tell it "weather first, then calculator" — it decided based on the task and tool results.

---

## Self-Check Questions

1. What happens if you don't add `response.content` to the history before `tool_result`? *(Claude won't see its previous request and the API will return an error — role order violated)*

2. Why is `tool_use_id` mandatory in `tool_result`? *(In parallel calls of multiple tools, Claude must know which result belongs to which request)*

3. The agent called 3 tools in parallel. How many elements will be in `tool_results`? *(3 — one for each call)*

---

## Relation to the Exam

**Typical Question:** The agent sometimes doesn't call `get_customer` before `process_refund`. How to fix?

- ❌ Improve system prompt — probabilistic matching, unreliable
- ❌ Add few-shot examples — same issue
- ✅ Programmatic precondition: block `process_refund` until an ID is received from `get_customer`

**Principle:** when a business rule requires **guaranteed** compliance — use programmatic control, not prompts.

---

*Next step: L1.2 — Multi-agent orchestration (coordinator + sub-agents)*

---

## Appendix: Who generates `tool_use_id`?

`tool_use_id` is generated by **Claude** — not us. We only read it from the response and return it back.

### Sequence

```
1. We send a request to Claude
         ↓
2. Claude returns a response with an ID it generated:
   {
     "type": "tool_use",
     "id": "toolu_01XyzAbc123",   ← Claude generated this ID
     "name": "get_weather",
     "input": {"city": "London"}
   }
         ↓
3. We execute get_weather("London"), get the result
         ↓
4. We send the result back with the SAME id:
   {
     "type": "tool_result",
     "tool_use_id": "toolu_01XyzAbc123",  ← taken from step 2, not invented
     "content": '{"temp": 12}'
   }
```

### In Code

```python
for block in response.content:
    if block.type == "tool_use":
        result = execute_tool(block.name, block.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,   # ← read from block, do not generate yourself
            "content": result
        })
```

### Why it's needed — parallel calls

If Claude calls two tools at once, ID is the only way to match results:

```
Claude requests:
  block[0]: id="toolu_AAA"  name="get_weather"  input={"city": "London"}
  block[1]: id="toolu_BBB"  name="calculate"    input={"expression": "12*9/5+32"}

We respond:
  {tool_use_id: "toolu_AAA", content: '{"temp": 12}'}
  {tool_use_id: "toolu_BBB", content: '{"result": 53.6}'}
```

Without `id`, Claude wouldn't know which result is from which call — especially if both returned just a number.

---

## Appendix 2: `input_schema` with multiple parameters

In the lecture example, each tool took one parameter. In practice, there are often several.

### Structure

```python
{
    "name": "create_order",
    "description": "Creates a new order for a customer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Customer ID from the database"
            },
            "product_id": {
                "type": "string",
                "description": "Product ID to order"
            },
            "quantity": {
                "type": "integer",
                "description": "Number of items, must be >= 1"
            },
            "discount_code": {
                "type": "string",
                "description": "Optional promo code, e.g. 'SAVE10'"
            }
        },
        "required": ["customer_id", "product_id", "quantity"]
        # discount_code is missing from required → optional parameter
    }
}
```

### Rule: `required` vs optional fields

| In `required` | Not in `required` |
|---|---|
| Claude MUST pass | Claude passes only if it exists in context |
| Call impossible without them | Absence is normal |

### How Claude will call the tool

```python
# Without discount code:
block.input == {
    "customer_id": "usr_123",
    "product_id":  "prd_456",
    "quantity":    2
}

# With discount code:
block.input == {
    "customer_id": "usr_123",
    "product_id":  "prd_456",
    "quantity":    2,
    "discount_code": "SAVE10"
}
```

### Handler function

```python
def create_order(customer_id: str, product_id: str,
                 quantity: int, discount_code: str = None) -> dict:
    # discount_code=None — default for optional parameter
    ...
```

The dispatcher calls via `**block.input` — all parameters are passed as keyword arguments:

```python
result = create_order(**block.input)
```
