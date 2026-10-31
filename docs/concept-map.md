# Course concept map

Where each topic from the three courses is demonstrated in this repo.

## Claude 101
| Topic | Proof in repo |
|-------|---------------|
| Effective prompting (role, structure, examples, unknowns) | `examples/claude_101/prompt_patterns.py` |
| Projects with custom instructions + knowledge | `claude_projects/*.md` |
| Everyday engineering workflows (review, RCA, docs) | `.claude/skills/*`, `claude_projects/*` |
| Reasoning, files and vision | `examples/api/06_vision_and_pdf.py`, `08_thinking_and_effort.py` |
| Connecting tools (connectors / MCP) | `examples/mcp/*` |
| Responsible use: verify claims, mask data, label guesses | Rules inside every skill and project file |

## Claude Code 101
| Topic | Proof in repo |
|-------|---------------|
| CLAUDE.md project memory | `CLAUDE.md`, `templates/CLAUDE.*.md` |
| Skills | `.claude/skills/` (6 skills, one with a helper script and one with a template) |
| Subagents | `.claude/agents/` (5 agents with scoped tools and models) |
| Slash commands with arguments and shell pre-run | `.claude/commands/` |
| Hooks (block, protect, audit) | `.claude/hooks/`, `.claude/settings.json`, `tests/test_hooks.py` |
| Permissions allow / deny | `.claude/settings.json` |
| MCP servers in a project | `.mcp.json`, `examples/mcp/` |
| Plan, test and verify before declaring done | "Definition of done" in `CLAUDE.md`; `scripts/validate_claude_assets.py` |

## Building with the Claude API
| Topic | Proof in repo |
|-------|---------------|
| Messages, system prompts, multi-turn | `examples/api/01_first_message.py` |
| Streaming | `02_streaming.py` |
| Structured outputs | `03_structured_output.py`, `src/playbook/workflows.py` |
| Tool use: manual loop and tool runner | `04_`, `05_`, `src/playbook/tools.py` |
| Multimodal | `06_vision_and_pdf.py` |
| Prompt caching | `07_prompt_caching.py` |
| Extended thinking and effort | `08_thinking_and_effort.py` |
| Batches | `09_batches.py` |
| Citations and RAG | `10_citations.py`, `11_rag_lite.py`, `src/playbook/rag.py` |
| Workflows vs agents | `12_workflows.py`, `src/playbook/workflows.py` |
| Prompt evaluation | `13_prompt_evals.py`, `src/playbook/evals.py` |
| Server tools (code execution, web search) | `14_server_tools.py` |
| Errors, retries, token counting, cost | `15_errors_and_cost.py` |
| MCP: server, client, SDK helpers, remote connector | `examples/mcp/` |
