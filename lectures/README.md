# Claude Code Architecture (CCA) Certification Course Program

## Course Overview
This course provides a comprehensive deep dive into the architecture, orchestration, and optimization of AI agents using Claude Code. It covers the full spectrum from basic agent loops to complex multi-agent systems, tool integration via MCP, and advanced prompt engineering for reliability and structured output.

**Total Duration:** Approximately 3-4 weeks.

---

## Curriculum

### Domain 1: Agent Architecture & Orchestration
| Lecture | Duration | Description |
| :--- | :---: | :--- |
| **L1.1 Agent Loop** | ~3h | Focuses on the fundamental "Request-Tool-Response" cycle. It covers `stop_reason` (tool_use vs end_turn), the importance of dialogue history, and the use of `tool_use_id` to link requests to results. |
| **L1.2 Multi-Agent Orchestration** | ~5h | Introduces the "Hub and Spoke" pattern using a Coordinator and specialized sub-agents. It covers the `Task` tool for spawning isolated sub-agents and the mechanics of explicit context transfer. |
| **L1.3 Hooks & Decomposition** | ~4h | Covers `PreToolUse` and `PostToolUse` hooks for policy enforcement and data normalization. It contrasts "Prompt Chaining" (fixed steps) with "Dynamic Decomposition" (adaptive steps). |

### Domain 2: Tool Design & MCP Integration
| Lecture | Duration | Description |
| :--- | :---: | :--- |
| **L2.1 Tool Design** | ~4h | Emphasizes that `description` is the primary routing mechanism. It covers structured error responses (transient, validation, permission, business) and the use of `tool_choice` (`auto`, `any`, `tool`) for deterministic behavior. |
| **L2.2 MCP Integration** | ~6h | Explores the Model Context Protocol (MCP). It covers the distinction between MCP Tools (actions) and MCP Resources (static data), configuration scoping (`.mcp.json` vs `~/.claude.json`), and secure secret handling using environment variables. |

### Domain 3: Claude Code Configuration & Workflows
| Lecture | Duration | Description |
| :--- | :---: | :--- |
| **L3.1 Claude Code Configuration** | ~4h | Details the hierarchy of `CLAUDE.md` (User -> Project -> Directory) and the use of `.claude/rules/` with glob patterns for conditional instruction loading. It also covers custom commands and skills. |
| **L3.2 Plan Mode & CI/CD** | ~3h | Focuses on the `/plan` workflow for high-risk architectural changes and non-interactive mode (`claude -p`) for CI/CD pipelines, including JSON output and schema enforcement. |

### Domain 4: Prompt Engineering & Structured Output
| Lecture | Duration | Description |
| :--- | :---: | :--- |
| **L4.1 Prompt Engineering** | ~4h | Covers high-impact techniques: Few-shot prompting, Chain-of-Thought (CoT), and the use of XML tags. It emphasizes explicit categorical criteria over vague instructions. |
| **L4.2 Structured Output** | ~5h | Focuses on using `tool_use` and JSON schemas for machine-readable output. It covers the validation-retry loop, nullable fields, and field-level confidence scores for human review. |
| **L4.3 Batch Processing** | ~3h | Explores the Message Batches API for high-volume, asynchronous processing, focusing on cost reduction (50% discount) and the use of `custom_id` for result mapping. |
| **L4.4 Multi-Pass Review** | ~4h | Addresses "confirmation bias" in self-correction. It advocates for independent reviewer instances and multi-pass architectures (Local Pass $\to$ Integration Pass). |

### Domain 5: Context Management & Reliability
| Lecture | Duration | Description |
| :--- | :---: | :--- |
| **L5.1 Context Reliability** | ~4h | Tackles the "Lost in the Middle" effect. It introduces the `<case facts>` block for persisting critical data and deterministic escalation triggers (policy gaps, no progress) instead of LLM self-assessment. |

### Exam Preparation & Review
| Lecture | Duration | Description |
| :--- | :---: | :--- |
| **LR1 Exam Traps** | ~6h | A targeted review of non-intuitive patterns, focusing on "Static vs Dynamic" routing and the difference between `/compact` and `Explore` sub-agents. |
| **LR2 Mock 3 Concepts** | ~6h | Covers advanced MCP error semantics, tool output trimming middleware, and "Phase-based" agents. |
