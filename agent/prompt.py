from runner.config import BudgetConfig
from runner.manifests import TaskManifest


def build_system_prompt(budget: BudgetConfig) -> str:
    return f"""You are an autonomous Python coding agent.
Your objective is to solve the task described below by inspecting files, editing code with patch diffs, and verifying your work with unit tests.

You must respond ONLY with a single JSON object conforming to one of these 5 action schemas:

1. List repository files:
{{"action": "list_files"}}

2. Read a file:
{{"action": "read_file", "path": "relative/path/to/file.py"}}

3. Apply a unified diff patch to edit files:
{{"action": "apply_patch", "patch": "--- a/file.py\\n+++ b/file.py\\n@@ -1,2 +1,2 @@\\n-old line\\n+new line\\n"}}

4. Run task unit tests:
{{"action": "run_tests"}}

5. Finish interaction:
{{"action": "finish", "summary": "Brief explanation of your fix"}}

STRICT RULES:
- Output ONLY raw JSON. Do NOT wrap your output in Markdown code blocks (```json ... ```).
- Output exactly ONE action JSON object per turn.
- No general shell access or arbitrary command execution is available.
- You have a budget of at most {budget.max_turns} turns.
- 'finish' is advisory; final evaluation will run fresh pytest execution independently.
"""


def build_task_prompt(manifest: TaskManifest, file_listing: str) -> str:
    instruction_text = manifest.instruction()
    return f"""Task Category: {manifest.category}
Task ID: {manifest.task_id}

INSTRUCTIONS:
{instruction_text}

INITIAL REPOSITORY FILES:
{file_listing}
"""


def bounded_observation(obs_str: str, max_bytes: int = 98304) -> str:
    obs_bytes = obs_str.encode("utf-8")
    if len(obs_bytes) <= max_bytes:
        return obs_str

    half = max_bytes // 2
    head = obs_bytes[:half].decode("utf-8", errors="replace")
    tail = obs_bytes[-half:].decode("utf-8", errors="replace")
    return f"{head}\n\n[... OUTPUT TRUNCATED DUE TO SIZE LIMIT ...]\n\n{tail}"
