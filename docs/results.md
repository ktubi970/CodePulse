# Benchmark results — October 2026

Machine: Windows 11 desktop, NVIDIA GeForce RTX 2070 (8 GB). Generated with
`codepulse report --output docs/results.md` from the SQLite results of `codepulse batch`.

168 runs (14 models x 12 tasks, latest run per pair), recorded 2026-10-22 to 2026-10-23.

Ollama 0.40.8 · Python 3.12.10 · Windows-11-10.0.26200-SP0

Budget: `context_tokens=8192`, `max_output_tokens=1024`, `max_turns=12`, `response_timeout_s=120.0`, `run_timeout_s=1800.0`, `seed=42`, `temperature=0.0`, `test_timeout_s=30.0`

| Rank | Model | Solved | Success rate | Median run time |
|---:|---|---:|---:|---:|
| 1 | `qwen2.5-coder:3b` | 7/12 | 58% | 19.6 s |
| 2 | `deepseek-coder:1.3b` | 3/12 | 25% | 9.3 s |
| 3 | `qwen3:1.7b` | 2/12 | 17% | 12.6 s |
| 4 | `gemma2:2b` | 2/12 | 17% | 16.9 s |
| 5 | `qwen2.5:1.5b` | 2/12 | 17% | 41.4 s |
| 6 | `smollm2:1.7b` | 1/12 | 8% | 7.4 s |
| 7 | `qwen3:0.6b` | 1/12 | 8% | 9.5 s |
| 8 | `qwen2.5-coder:1.5b` | 1/12 | 8% | 10.8 s |
| 9 | `granite-code:3b` | 1/12 | 8% | 12.9 s |
| 10 | `llama3.2:1b` | 1/12 | 8% | 13.5 s |
| 11 | `qwen2.5-coder:0.5b` | 0/12 | 0% | 10.3 s |
| 12 | `gemma3:1b` | 0/12 | 0% | 12.5 s |
| 13 | `codegemma:2b` | 0/12 | 0% | 19.3 s |
| 14 | `starcoder2:3b` | 0/12 | 0% | 28.9 s |

### Per task

| Task | Solved by |
|---|---:|
| `bug_cache_key` | 1/14 models |
| `bug_off_by_one` | 9/14 models |
| `csv_clean_contacts` | 0/14 models |
| `csv_sales_summary` | 0/14 models |
| `feature_chunked` | 1/14 models |
| `feature_slugify` | 1/14 models |
| `parse_config_version` | 0/14 models |
| `parse_event_payload` | 1/14 models |
| `refactor_normalize_record` | 3/14 models |
| `refactor_pricing` | 1/14 models |
| `test_parse_bool` | 1/14 models |
| `test_safe_divide` | 3/14 models |

### Failure modes

| Status | Runs |
|---|---:|
| `tests_failed` | 146 |
| `generation_error` | 1 |

### Matrix

| Model | `bug_cache_key` | `bug_off_by_one` | `csv_clean_contacts` | `csv_sales_summary` | `feature_chunked` | `feature_slugify` | `parse_config_version` | `parse_event_payload` | `refactor_normalize_record` | `refactor_pricing` | `test_parse_bool` | `test_safe_divide` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `qwen2.5-coder:3b` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| `deepseek-coder:1.3b` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| `qwen3:1.7b` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| `gemma2:2b` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `qwen2.5:1.5b` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `smollm2:1.7b` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `qwen3:0.6b` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `qwen2.5-coder:1.5b` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `granite-code:3b` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `llama3.2:1b` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `qwen2.5-coder:0.5b` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `gemma3:1b` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `codegemma:2b` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `starcoder2:3b` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

## Notes

- **One run per model and task, at temperature 0.** A one-task difference is about 8 percentage
  points; treat close scores as ties.
- **Run times are wall-clock times** on a desktop whose GPU was occasionally shared with other
  workloads. Use them as an order of magnitude, not as a speed benchmark.
- **The batch ran in several sittings.** The local Ollama server crashed once and the run was resumed
  with identical parameters (see the budget line above); the report keeps the latest run of each
  model and task.
- `starcoder2:3b` and `codegemma:2b` are base code-completion models, not instruction-tuned
  assistants. 36% of `starcoder2:3b`'s replies were invalid actions and it never edited a file; on
  `csv_clean_contacts` it looped until Ollama aborted the generation (`generation_error`).
  `codegemma:2b` followed the protocol but none of its 12 edits passed the tests.
- Across the 168 runs, models made 181 accepted `write_file` edits and **zero** valid
  `apply_patch` diffs. 60 of the 147 failed runs never edited a file.
