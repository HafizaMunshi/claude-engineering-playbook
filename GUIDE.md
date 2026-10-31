# Claude Engineering Playbook - The Guide

A tour of everything in this repository: what each skill, agent, command, hook, server
and example is, why it exists, how to run it, and how to extend it.

> **Independent learning project.** It is not affiliated with or endorsed by Anthropic.
> All data is synthetic and every example is generic - no employer code, data or credentials.

---

## Contents

1. [What this repo is](#1-what-this-repo-is)
2. [Five-minute quick start](#2-five-minute-quick-start)
3. [Map of the repository](#3-map-of-the-repository)
4. [Claude Code toolkit (`.claude/`)](#4-claude-code-toolkit-claude)
   - [Skills](#41-skills) - [Subagents](#42-subagents) - [Slash commands](#43-slash-commands)
   - [Hooks](#44-hooks) - [Settings and permissions](#45-settings-and-permissions-settingsjson)
   - [Project memory (CLAUDE.md) and templates](#46-project-memory-claudemd-and-templates)
5. [MCP servers and clients (`examples/mcp/`)](#5-mcp-servers-and-clients-examplesmcp)
6. [Claude API examples (`examples/api/`)](#6-claude-api-examples-examplesapi)
7. [Claude 101: prompt patterns and Projects](#7-claude-101-prompt-patterns-and-projects)
8. [The Python library (`src/playbook/`)](#8-the-python-library-srcplaybook)
9. [Tests and quality checks](#9-tests-and-quality-checks)
10. [How to extend the playbook](#10-how-to-extend-the-playbook)
11. [Troubleshooting](#11-troubleshooting)
12. [Glossary](#12-glossary)

---

## 1. What this repo is

A set of **working, tested examples** of how an engineer can use Claude day to day. It is organised
around three learning areas:

| Area | What you will find | Where |
|------|--------------------|-------|
| **Claude 101** - using Claude well | Reusable prompt templates and instructions for Claude Projects | `examples/claude_101/`, `claude_projects/` |
| **Claude Code 101** - Claude in your repo | Skills, subagents, slash commands, hooks, permissions, project memory, MCP config | `.claude/`, `.mcp.json`, `CLAUDE.md`, `templates/` |
| **Building with the Claude API** - in your own software | 15 focused API examples, an agent loop, workflow patterns, evals, retrieval, two MCP servers | `examples/api/`, `examples/mcp/`, `src/playbook/` |

**Design principles**

- **Safe by default.** Database access is read-only; hooks block destructive commands and secrets;
  fixes for data are produced as text for a human to run, never executed by the AI.
- **Testable.** All logic that calls Claude takes a `client` argument, so tests inject a fake and run
  offline in seconds.
- **Least privilege.** Every subagent lists exactly the tools it needs.
- **Explained.** Every source file begins with a docstring saying what it is and why it exists.

---

## 2. Five-minute quick start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 2. Install the package and test tools
pip install -e ".[dev]"

# 3. Run the offline tests (no API key needed)
pytest

# 4. Lint the Claude Code configuration
python scripts/validate_claude_assets.py

# 5. See MCP working end to end (still no API key)
python examples/mcp/client_demo.py
```

To run the live examples you need an API key:

```bash
export ANTHROPIC_API_KEY=your-key      # Windows PowerShell: $env:ANTHROPIC_API_KEY="your-key"
python examples/api/01_first_message.py
```

Optional environment variables (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | none | Credentials for live examples. Never commit it. |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Model for demanding tasks |
| `CLAUDE_FAST_MODEL` | `claude-haiku-5-5` | Cheap model for classification, routing and judging |

---

## 3. Map of the repository

```text
claude-engineering-playbook/
|-- README.md                  short overview
|-- GUIDE.md                   this document
|-- CLAUDE.md                  project memory that Claude Code reads every session
|-- pyproject.toml             package metadata and dependencies
|-- .env.example               template for local secrets (copy to .env; .env is gitignored)
|-- .mcp.json                  MCP servers Claude Code should start for this project
|-- .claude/
|   |-- settings.json          permissions + hook wiring
|   |-- skills/                6 skills (folder + SKILL.md each)
|   |-- agents/                5 subagents (one markdown file each)
|   |-- commands/              4 slash commands (one markdown file each)
|   `-- hooks/                 3 hook scripts (Python)
|-- templates/                 CLAUDE.md templates for 4 project types
|-- claude_projects/           custom instructions for 3 Claude.ai Projects
|-- docs/                      concept map, Claude Code notes, API cheat-sheet
|-- examples/
|   |-- claude_101/            prompt patterns
|   |-- api/                   15 numbered API examples
|   `-- mcp/                   2 servers, 2 clients, 1 remote-connector example
|-- src/playbook/              shared, tested Python library
|-- scripts/                   validate_claude_assets.py
`-- tests/                     58 offline tests
```

---

## 4. Claude Code toolkit (`.claude/`)

Claude Code looks in `.claude/` for project-specific behaviour. Files here are committed so every
teammate gets the same setup.

### 4.1 Skills

A **skill** is a folder containing a `SKILL.md`: a short header (`name`, `description`) followed by
step-by-step instructions. Claude reads only the names and descriptions at the start of a session and
loads the full instructions **only when your request matches**. That keeps context small, so you can
have many skills.

> The `description` is the trigger. It must say *when* to use the skill.

| Skill | Use it when you say... | What it makes Claude do |
|-------|------------------------|--------------------------|
| **pr-review** | "Review my branch / this diff" | Restates the change's intent, checks correctness, security, contracts, tests and maintainability in order, and reports at most 10 findings as `[blocker/major/nit] file:line - problem - fix`. It does not edit files during a review. |
| **incident-rca** | "Write a postmortem", "why did the outage happen?" | Builds an evidence-backed timeline, runs five whys down to a process gap, lists contributing factors, and proposes actions with an owner role and a measurable done-condition. Uses `templates/rca.md`. Blameless wording is mandatory. |
| **readonly-db-investigation** | "Why are there duplicate rows?", "check the data" | States a hypothesis, reads the schema, runs the smallest possible SELECT through `scripts/safe_query.py` (SELECT-only, read-only connection, row cap), and reports what the result proves and does not prove. Any fix is delivered as text: a verify query, a fix statement, a validate query. |
| **write-unit-tests** | "Add tests for this", "cover this bug" | Tests behaviours rather than methods, writes the failing test first for bugs, mocks only true boundaries (network, clock, DB), runs the suite and reports the command and result. |
| **adr-writer** | "Record this decision" | Creates the next numbered Architecture Decision Record in `docs/adr/` with context, decision, real alternatives and consequences. Accepted ADRs are superseded, never edited. |
| **release-notes** | "Draft release notes from v1.2 to v1.3" | Reads git history, drops noise, groups changes as Added / Changed / Fixed / Security / Breaking, rewrites them as user-visible impact and adds upgrade notes. |

**Bundled files.** `incident-rca` ships a template at `.claude/skills/incident-rca/templates/rca.md`.
`readonly-db-investigation` ships `scripts/safe_query.py`, a standalone, standard-library-only script:

```bash
python .claude/skills/readonly-db-investigation/scripts/safe_query.py examples/mcp/sample.sqlite --schema
python .claude/skills/readonly-db-investigation/scripts/safe_query.py examples/mcp/sample.sqlite \
  "SELECT customer_id, COUNT(*) n FROM subscriptions WHERE status='active' GROUP BY customer_id HAVING n > 1"
```

### 4.2 Subagents

A **subagent** is a specialist that Claude can delegate to. It works in its **own context window**
and returns only a summary, so noisy work (reading dozens of files) does not clutter your main chat.
Each agent file declares its `tools` (what it may do) and `model` (cost / capability).

| Agent | Purpose | Tools | Model | Why those tools |
|-------|---------|-------|-------|-----------------|
| **code-reviewer** | Review uncommitted changes before commit; ranked findings with file:line evidence | Read, Grep, Glob, Bash | sonnet | Needs `git diff` (Bash) but cannot edit - a reviewer must not change code |
| **test-writer** | Add unit or regression tests and run them | Read, Grep, Glob, Edit, Write, Bash | sonnet | Writes and runs tests; instructed never to edit production code |
| **security-auditor** | Trace untrusted input to dangerous sinks (SQL, shell, URLs, paths) | Read, Grep, Glob | opus | Strictly read-only; hardest reasoning gets the strongest model |
| **debugger** | Find root causes of failures by reproducing, narrowing and testing hypotheses | Read, Grep, Glob, Bash, Edit | opus | Must reproduce (Bash) and fix (Edit); stops after three disproved hypotheses |
| **docs-writer** | Write READMEs and runbooks from the real code | Read, Grep, Glob, Edit, Write | haiku | Simple writing; no Bash so it cannot run unverified commands |

### 4.3 Slash commands

A **slash command** is a saved prompt you trigger by typing `/name`. The filename is the command name.

| Command | Example | What it does |
|---------|---------|--------------|
| `/pr-summary [base]` | `/pr-summary main` | Runs `git log` and `git diff --stat` first, then drafts a PR title, what changed, why, how to test and risks. |
| `/triage-bug <text>` | `/triage-bug Export spins forever on large ranges` | Returns severity, likely code area (it searches the repo), repro steps, missing information and next action. |
| `/standup` | `/standup` | Reads your last 24 hours of commits plus working-tree status and writes a 60-word standup. |
| `/explain-diff <path>` | `/explain-diff src/playbook/tools.py` | Attaches the file and explains it to a new teammate. |

Syntax used in the command files: `$ARGUMENTS` inserts what you typed; a line starting with `!`
followed by a backticked command runs it **before** the prompt is sent; `@path` attaches a file;
`allowed-tools` limits which tools the command may use without prompting.

### 4.4 Hooks

A **hook** is a script Claude Code runs automatically at a lifecycle event. It receives the event as
JSON on standard input. For a `PreToolUse` hook, **exit code 2 blocks the action** and whatever the
script prints to standard error is shown to Claude so it can choose a safer approach. Exit code 0 allows.

Hooks are for rules that must *always* hold - instructions in a prompt are requests, hooks are rules.

| Hook | Runs | Blocks / records |
|------|------|------------------|
| `block_dangerous_bash.py` | Before any Bash command | `rm -rf` (any flag order), `git push --force` or `-f`, `git reset --hard`, `DROP TABLE` / `DROP DATABASE`, piping `curl`/`wget` into a shell, `chmod -R 777` |
| `protect_secrets.py` | Before Edit or Write | Files named `.env`, `.npmrc`, `.pypirc`, `id_rsa`, `id_ed25519`, `credentials`, `*.pem`, `*.key`; content that looks like an Anthropic key, an AWS access key or a private-key header |
| `log_tool_use.py` | After every tool call | Appends a one-line audit record (UTC time, tool, first 120 characters of input) to `.claude/hooks/tool-use.log` (gitignored). Never blocks. |

> **Honest note:** these are deny-lists. They catch common accidents but are not a security boundary -
> a determined command can evade a regex. Combine with permissions, sandboxing and code review.

Test a hook by hand exactly as Claude Code would call it:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git reset --hard HEAD~1"}}' \
  | python .claude/hooks/block_dangerous_bash.py ; echo "exit code: $?"
# prints "Blocked by project hook: hard reset discards work..." and exit code: 2
```

### 4.5 Settings and permissions (`settings.json`)

JSON cannot contain comments, so here is `.claude/settings.json` explained:

| Section | Entry | Meaning |
|---------|-------|---------|
| `permissions.allow` | `Bash(git status:*)`, `Bash(git diff:*)`, `Bash(git log:*)` | Read-only git commands run without asking |
| | `Bash(pytest:*)`, `Bash(python scripts/validate_claude_assets.py:*)` | Tests and the linter run without asking |
| | `Read`, `Grep`, `Glob` | Reading and searching are always safe |
| `permissions.deny` | `Read(./.env)`, `Read(./.env.*)` | Claude may never read local secret files |
| | `Bash(git push --force:*)`, `Bash(rm -rf:*)` | Destructive commands are refused. **Deny always beats allow.** |
| `hooks.PreToolUse` | matcher `Bash` -> `block_dangerous_bash.py` | Check every shell command before it runs |
| | matcher `Edit` or `Write` (written `Edit\|Write` in the file) -> `protect_secrets.py` | Check every file edit before it is applied |
| `hooks.PostToolUse` | matcher `*` -> `log_tool_use.py` | Record every tool call afterwards |

Anything not listed in `allow` or `deny` asks you for confirmation.

### 4.6 Project memory (`CLAUDE.md`) and templates

`CLAUDE.md` is loaded into every session. This repo's file records the layout, commands, conventions
and definition of done. The `templates/` folder holds ready-to-copy starting points:

| Template | For | Key rules it sets |
|----------|-----|-------------------|
| `CLAUDE.backend-service.md` | REST / backend services | Validate every input at the edge, append-only DB migrations, outbound-URL allow-lists, no AI-run migrations |
| `CLAUDE.data-pipeline.md` | Batch data pipelines | Idempotent re-runs, row-count checks, dry-run by default, SELECT-only investigation |
| `CLAUDE.frontend-app.md` | React / TypeScript apps | Strict types, design-system first, one shared HTTP client, all UI states |
| `CLAUDE.infra-as-code.md` | Terraform / cloud | Claude may `plan` but never `apply` or `destroy`; tag everything; least-privilege IAM |

---

## 5. MCP servers and clients (`examples/mcp/`)

**MCP (Model Context Protocol)** is an open standard for connecting AI apps to tools and data. You write
one *server*; any compatible *client* (Claude Code, Claude Desktop, your own app) can use it.
A server can offer three kinds of capability:

| Primitive | Who triggers it | Purpose |
|-----------|-----------------|---------|
| **Tool** | The model | Do something or fetch something |
| **Resource** | The app or user | Read-only context to attach |
| **Prompt** | The user | A reusable, parameterised prompt template |

### Servers

| File | Registered as | Offers |
|------|---------------|--------|
| `db_server.py` | `dev-db` | Tools `list_tables` and `query` (single SELECT, max 100 rows, read-only connection); resource `schema://main`; prompt `investigate_duplicates(table, key_column)` |
| `devtools_server.py` | `dev-tools` | Tools `summarize_log` (level counts and most frequent error messages) and `next_version` (semantic-version bump) |

Both run over **stdio**: Claude Code starts them as child processes using `.mcp.json`:

| `.mcp.json` field | Meaning |
|-------------------|---------|
| `mcpServers.dev-db.command` / `args` | Run `python examples/mcp/db_server.py --db examples/mcp/sample.sqlite` |
| `mcpServers.dev-tools.command` / `args` | Run `python examples/mcp/devtools_server.py` |

The sample database is created automatically with synthetic data. It deliberately contains one
**data-quality bug** - customer 2 has two *active* subscriptions - so you have something real to find.

### Clients and connection methods

| File | Needs API key | What it demonstrates |
|------|---------------|----------------------|
| `client_demo.py` | No | A bare MCP client over stdio: connect, list tools/resources/prompts, call `query`. Prints the duplicate-subscription finding. |
| `client_with_claude.py` | Yes | Hands the server's tools to Claude through the SDK's MCP helpers and asks it to find the duplicate. |
| `remote_connector.py` | Yes + a remote server URL | The API's MCP connector, where Anthropic's side connects to a remote HTTPS server. Needs both `mcp_servers` and an `mcp_toolset` entry. |

```bash
python examples/mcp/client_demo.py
# tools: ['list_tables', 'query']
# resources: ['schema://main']
# prompts: ['investigate_duplicates']
# duplicate_active: [{"customer_id": 2, "n": 2}]
```

> **Rule for stdio servers:** never print to standard output. It carries the protocol; use standard
> error for logs.

---

## 6. Claude API examples (`examples/api/`)

Each script demonstrates one concept in a short file. Run from the repository root with
`ANTHROPIC_API_KEY` set. Examples that need an input file say so in their header.

| # | File | Concept | Run it to see |
|---|------|---------|---------------|
| 01 | `01_first_message.py` | Messages, system prompt, multi-turn memory, token usage | A two-turn conversation where the second answer depends on the first |
| 02 | `02_streaming.py` | Streaming output | Text appearing token by token, then stop reason and token count |
| 03 | `03_structured_output.py` | Schema-enforced JSON via a Pydantic model | A messy chat message turned into a validated bug report |
| 04 | `04_tool_use_manual_loop.py` | Hand-written agent loop with a read-only database and a calculator | Each tool call printed, then a final answer with invoice totals |
| 05 | `05_tool_runner.py` | SDK tool runner with `@beta_tool` | The SDK running the loop for `git_log` and `count_lines` tools |
| 06 | `06_vision_and_pdf.py` | Images and PDFs as input | `python examples/api/06_vision_and_pdf.py diagram.png "Explain this"` |
| 07 | `07_prompt_caching.py` | Prompt caching | Cache-written tokens on call 1, cache-read tokens on call 2 |
| 08 | `08_thinking_and_effort.py` | Adaptive thinking and the effort dial | The same puzzle at `low` and `high` effort with token counts |
| 09 | `09_batches.py` | Message Batches (cheaper, asynchronous) | Four commit messages labelled in bulk, keyed by `custom_id` |
| 10 | `10_citations.py` | Answers that quote their source | Text with the exact cited passage |
| 11 | `11_rag_lite.py` | Retrieval-augmented generation without a vector DB | Top-matching chunks from `docs/`, then a cited answer |
| 12 | `12_workflows.py` | Chaining, routing, parallelization, evaluator-optimizer | All four patterns on realistic inputs |
| 13 | `13_prompt_evals.py` | Measuring prompts with a labelled dataset | A leaderboard comparing a vague and a rubric prompt |
| 14 | `14_server_tools.py` | Server-side code execution and web search | Percentiles computed in a sandbox; a cited web answer |
| 15 | `15_errors_and_cost.py` | Typed errors, retries, token counting | An estimated cost before sending, then a safely handled call |

**Conventions used throughout**

- Models come from `playbook.common.model()` / `fast_model()` - no hard-coded model names in examples.
- Current models reject `temperature`, `top_p` and `top_k`, do not support assistant prefill and may reject
  forced `tool_choice`; the examples use prompts, structured outputs, `effort` and `tool_choice: auto`.
- Always check `stop_reason` before reading a response (`max_tokens`, `refusal`, `tool_use`...).

---

## 7. Claude 101: prompt patterns and Projects

### Prompt patterns (`examples/claude_101/prompt_patterns.py`)

```bash
python examples/claude_101/prompt_patterns.py                 # lists the patterns
python examples/claude_101/prompt_patterns.py xml_structure   # runs one
```

| Pattern | Problem it solves | Technique |
|---------|-------------------|-----------|
| `role_and_audience` | Answers pitched at the wrong level | Give a role and name the reader; cap length |
| `xml_structure` | Data mixed with instructions; prompt injection | Wrap data in tags and say it is data, not instructions |
| `few_shot` | Inconsistent output format | Show examples instead of describing the format |
| `reason_then_answer` | Snap judgements on trade-offs | Reason in one tag, answer in another |
| `admit_unknowns` | Made-up answers | Define an exact reply for missing information |

### Claude Projects (`claude_projects/`)

Paste these into the **Custom instructions** field of a Project on claude.ai and upload your own
reference files as Project knowledge.

| File | Gives Claude the role of |
|------|--------------------------|
| `code-review-project.md` | A review partner with a fixed review order and finding format |
| `incident-commander-project.md` | An on-call assistant that maintains a status header and prefers reversible mitigations |
| `tech-writer-project.md` | A documentation writer that picks the right document form for the reader |

---

## 8. The Python library (`src/playbook/`)

Reusable code that the examples and tests import. After `pip install -e .` it is importable as `playbook`.

| Module | Responsibility | Key functions |
|--------|----------------|---------------|
| `common.py` | Client creation, model names from the environment, text extraction | `get_client`, `model`, `fast_model`, `text_of`, `ask` |
| `sqlguard.py` | Make SQL safe to hand to a model: single SELECT only, read-only connection, row cap | `validate_select`, `open_readonly`, `run_select`, `describe_schema`, `UnsafeSQL` |
| `tools.py` | Tool definitions, a safe calculator, the tool-execution wrapper and the agent loop | `safe_eval`, `make_toolset`, `execute_tool`, `run_agent_loop` |
| `workflows.py` | The four workflow patterns | `chain`, `route`, `parallelize`, `evaluate_optimize` |
| `evals.py` | Prompt evaluation harness with four graders | `Case`, `grade`, `run_eval`, `compare` |
| `rag.py` | Chunking, TF-IDF retrieval, prompt building | `chunk_text`, `retrieve`, `build_prompt`, `answer` |
| `sampledb.py` | Builds the synthetic SQLite database used by demos and tests | `build` |

**How the agent loop works** (`tools.run_agent_loop`):

1. Send the question plus the tool definitions.
2. If the reply's `stop_reason` is `tool_use`, run **every** requested tool.
3. Send **all** results back in a **single** user message, each tagged with the matching `tool_use_id`.
4. Failures are returned with `is_error: true` so the model can recover instead of the program crashing.
5. Repeat until the model answers, or stop after `max_turns` so a confused model cannot loop forever.

**How SQL safety layers up** (`sqlguard`): (1) syntax allow-list - one statement, must start with SELECT or WITH,
no write keywords; (2) the database connection itself is opened read-only; (3) at most 100 rows come back.
Either of the first two alone would be enough for the demo data; together they survive a bug in either.

---

## 9. Tests and quality checks

```bash
pytest                                     # 58 tests, offline, about 10 seconds
python scripts/validate_claude_assets.py   # lints .claude/ and .mcp.json
```

| Test file | What it protects |
|-----------|------------------|
| `test_sqlguard.py` | Reads are allowed, every kind of write is rejected, the connection is truly read-only, the sample bug is findable |
| `test_tools.py` | The calculator refuses code, tool errors go back to the model, parallel results return in one message, the loop is bounded |
| `test_workflows.py` | Each workflow pattern wires its steps correctly |
| `test_evals_and_rag.py` | Graders, pass-rate maths, retrieval ranking, chunk overlap, citation prompt |
| `test_hooks.py` | Hooks block what they should and allow what they should, using real stdin/exit-code contracts |
| `test_assets_and_mcp.py` | The linter passes on this repo and fails on a bad skill; the MCP server works over a real stdio connection |

**The fake client.** `tests/conftest.py` provides `FakeClient`, which imitates `client.messages.create`
and `client.messages.parse` with scripted replies, so agent logic can be tested without network or cost.
Model *quality* is a separate concern, covered by evals (`examples/api/13_prompt_evals.py`).

**What the asset linter checks** (`scripts/validate_claude_assets.py`): skill name equals folder name and is
lowercase-hyphen; descriptions are long enough and say when to use the skill; every agent has a matching
filename, a description and an explicit `tools` list; commands have descriptions; `settings.json` is valid,
uses known hook events and points at scripts that exist; `.mcp.json` servers have commands and existing scripts.

---

## 10. How to extend the playbook

| I want to add... | Do this |
|------------------|---------|
| **A skill** | Create `.claude/skills/<name>/SKILL.md` with `name` (same as the folder) and a `description` that says *when* to use it. Put long reference material in sibling files. Run the linter. |
| **A subagent** | Create `.claude/agents/<name>.md` with `name` (same as filename), `description`, an explicit `tools:` list and a `model`. Give it the minimum tools. |
| **A slash command** | Create `.claude/commands/<name>.md` with a `description`; use `$ARGUMENTS`, `!` shell lines and `allowed-tools` as needed. |
| **A hook rule** | Add a `(regex, reason)` pair to `BLOCKED` in `block_dangerous_bash.py`, then add the command to the parameter list in `tests/test_hooks.py`. |
| **An agent tool** | Add a schema dict and a handler in `src/playbook/tools.py` (`make_toolset`), and a test in `tests/test_tools.py`. Treat all inputs as untrusted. |
| **An MCP tool** | Decorate a function with `@mcp.tool()` in a server file; keep the logic in a plain function so tests can call it directly. |
| **An API example** | Add `examples/api/NN_name.py` with a module docstring (what, why, how to run); keep logic that needs testing in `src/playbook/`. |
| **An eval case** | Append a `Case(input, expected, grader)` to the dataset in `13_prompt_evals.py`. |

Definition of done for any change: `pytest` green, linter clean, README or this guide updated.

---

## 11. Troubleshooting

| Symptom | Likely cause and fix |
|---------|----------------------|
| `ModuleNotFoundError: playbook` | Run `pip install -e .` from the repo root inside the virtual environment |
| `ImportError ... FastMCP` | You have MCP SDK v2, where the class is `MCPServer` (`from mcp.server.mcpserver import MCPServer`). This repo targets v2. |
| Anthropic `AuthenticationError` | `ANTHROPIC_API_KEY` is missing or wrong in the current shell |
| `400` complaining about `temperature` or prefill | Current models do not accept them; remove the parameter and steer with the prompt |
| Cache read tokens always 0 in example 07 | Something before the cached block changed between calls, or the prefix is shorter than the model's minimum cacheable length |
| MCP client hangs or prints garbled errors | A server printed to standard output. Send logs to standard error only. |
| A hook does nothing | Check that `python` is on your PATH (some systems only have `python3`) and that the script path in `settings.json` is correct |
| `sample.sqlite` looks wrong | Delete it; `db_server.py` or `python -m playbook.sampledb` recreates it |
| Linter says a hook script is missing | The path in `.claude/settings.json` is relative to the repo root; run the linter from there |

---

## 12. Glossary

| Term | Meaning |
|------|---------|
| **Agent** | A system where the model decides the next step by calling tools |
| **Workflow** | A system where your code decides the sequence of model calls |
| **Skill** | A folder with `SKILL.md` that Claude loads when your request matches its description |
| **Subagent** | A specialist assistant with its own context window and tool allow-list |
| **Slash command** | A saved prompt triggered by `/name` |
| **Hook** | A script run at a lifecycle event; exit code 2 on `PreToolUse` blocks the action |
| **MCP** | Model Context Protocol - a standard way to expose tools, resources and prompts to AI apps |
| **stdio transport** | MCP over a child process's standard input and output |
| **Prompt caching** | Reusing an unchanged prompt prefix at a fraction of the input cost |
| **Structured output** | A response forced to match a schema |
| **Effort** | A setting that trades answer thoroughness against token cost and speed |
| **RAG** | Retrieval-augmented generation - answering from retrieved documents |
| **TF-IDF** | A word-overlap scoring method that favours distinctive terms |
| **Eval** | A labelled dataset plus automatic grading used to compare prompts |
| **LLM-as-judge** | Using a model to grade another model's output |
| **Defence in depth** | Several independent safeguards, so one failure is not fatal |
| **Least privilege** | Granting only the access a task requires |
| **Idempotent** | Safe to run repeatedly with the same result |
