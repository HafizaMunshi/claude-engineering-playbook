# Claude API cheat-sheet

| Need | Use | Example |
|------|-----|---------|
| One answer | `messages.create` | `examples/api/01_first_message.py` |
| Live output | `messages.stream` + `get_final_message()` | `02_streaming.py` |
| Guaranteed JSON shape | `messages.parse(output_format=PydanticModel)` | `03_structured_output.py` |
| Call my code | tools + loop, or `tool_runner` | `04_`, `05_` |
| Images / PDFs | `image` / `document` content blocks | `06_vision_and_pdf.py` |
| Cheaper repeated context | `cache_control` on a stable prefix | `07_prompt_caching.py` |
| Hard reasoning | `thinking={"type":"adaptive"}` + `output_config.effort` | `08_thinking_and_effort.py` |
| Bulk, not urgent | `messages.batches` (50% cheaper) | `09_batches.py` |
| Trustworthy sourcing | document `citations` | `10_citations.py` |
| Your own corpus | retrieval then prompt | `11_rag_lite.py` |
| Multi-step flows | chain / route / parallelize / evaluator-optimizer | `12_workflows.py` |
| Know if a prompt improved | eval dataset + graders | `13_prompt_evals.py` |
| Run code, search web | server tools | `14_server_tools.py` |
| Failure handling, cost | typed errors, `count_tokens` | `15_errors_and_cost.py` |

## Rules of thumb
- The API is stateless; resend the history.
- Check `stop_reason` before trusting `content` (`max_tokens`, `refusal`, `tool_use`, `pause_turn`).
- Return all tool results for one turn in a single user message, matching each `tool_use_id`.
- Tool inputs come from a model: validate them like any untrusted input.
- Put stable content first, volatile content last, to make caching work.
- Do not use prefill or sampling parameters on current models; use structured outputs, prompts and effort.
