"""
Step 1.1: Agent Loop
=====================================
Demonstrates a basic agent loop:
  - Sending a request with tools
  - Checking stop_reason
  - Executing tools
  - Adding results to history
  - Repeating until end_turn
"""

import anthropic
import json

# ---------------------------------------------------------------------------
# 1. Simulate "backend" — functions that the agent can call
# ---------------------------------------------------------------------------

def get_weather(city: str) -> dict:
    """Weather API simulation."""
    fake_data = {
        "Kyiv": {"temp": -5, "condition": "snow"},
        "London": {"temp": 12, "condition": "rain"},
        "Tokyo":  {"temp": 18, "condition": "cloudy"},
    }
    return fake_data.get(city, {"error": f"City '{city}' not found"})


def calculate(expression: str) -> dict:
    """Simple calculator."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 2. Describe tools for Claude
#    [CRITICAL]: descriptions are the primary mechanism for LLM tool selection
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_weather",
        "description": (
            "Returns the current weather for a specified city. "
            "Use this when the user asks about weather, temperature "
            "or climatic conditions in a specific location. "
            "Supported cities: Kyiv, London, Tokyo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name in English (e.g., 'Kyiv')"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculate",
        "description": (
            "Calculates a mathematical expression and returns the result. "
            "Use only for mathematical calculations: addition, subtraction, "
            "multiplication, division, exponents. "
            "DO NOT use for retrieving data — only for numbers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression, e.g., '2 + 2' or '15 * 8'"
                }
            },
            "required": ["expression"]
        }
    }
]


# ---------------------------------------------------------------------------
# 3. Tool Dispatcher — executes what Claude requested
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Calls the required function and returns the result as a string."""
    print(f"  [EXEC] Executing tool: {tool_name}({tool_input})")

    if tool_name == "get_weather":
        result = get_weather(**tool_input)
    elif tool_name == "calculate":
        result = calculate(**tool_input)
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 4. AGENT LOOP — key pattern for the exam
# ---------------------------------------------------------------------------

def run_agent(user_message: str) -> str:
    """
    Runs the agent loop:
    1. Send request to Claude
    2. Check stop_reason
    3. If "tool_use" → execute tools, add to history, repeat
    4. If "end_turn" → return final response
    """
    client = anthropic.Anthropic()  # API key from ANTHROPIC_API_KEY env var

    # Dialogue history — accumulates between iterations
    messages = [
        {"role": "user", "content": user_message}
    ]

    print(f"\n{'='*60}")
    print(f"Request: {user_message}")
    print(f"{'='*60}")

    iteration = 0

    while True:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

        # Step 1: Send request to Claude
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            tools=TOOLS,
            messages=messages
        )

        print(f"stop_reason: {response.stop_reason}")

        # Step 2: Check stop_reason
        # ---------------------------------------------------------------
        # ANTIPATTERN [X]: checking response text, counting iterations
        # CORRECT [V]: check only stop_reason
        # ---------------------------------------------------------------

        if response.stop_reason == "end_turn":
            # Agent finished — extract final text
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text = block.text
                    break
            print(f"\n[OK] Final response: {final_text}")
            return final_text

        elif response.stop_reason == "tool_use":
            # Agent wants to call tools

            # Step 3a: Add assistant's response to history
            # (important: add the WHOLE content block, including tool_use)
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Step 3b: Execute all requested tools
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [CALL] Claude calls: {block.name}")

                    # Execute tool
                    result = execute_tool(block.name, block.input)

                    # Format result in a way Claude understands
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,  # [LINK] ID links request and result
                        "content": result
                    })

            # Step 3c: Add tool results to history
            # Now Claude "sees" them on the next iteration
            messages.append({
                "role": "user",
                "content": tool_results
            })

            # Step 4: Return to step 1 (continue loop)

        else:
            # Unexpected stop_reason (max_tokens, stop_sequence, etc.)
            print(f" [!] Unexpected stop_reason: {response.stop_reason}")
            break

    return "Agent finished without a final response"


# ---------------------------------------------------------------------------
# 5. Running examples
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Example 1: single tool
    run_agent("What is the weather in Kyiv?")

    # Example 2: two tools at once
    run_agent("What is the weather in Tokyo and how much is 37 * 48?")

    # Example 3: chain — result of one tool is needed for another
    run_agent(
        "Find the temperature in London, then calculate "
        "how much that is in Fahrenheit (formula: F = C * 9/5 + 32)"
    )
