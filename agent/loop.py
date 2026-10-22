from dataclasses import dataclass
import json
import time
from typing import Any

from agent.executor import ActionResult, TestResult, WorkspaceExecutor
from agent.ollama import OllamaClient, OllamaModel
from agent.prompt import bounded_observation, build_system_prompt, build_task_prompt
from agent.protocol import Finish, ProtocolError, action_json_schema, parse_action
from runner.config import BudgetConfig
from runner.manifests import TaskManifest
from runner.storage import ActionRecord, ResultStore, RunRecord


@dataclass(frozen=True, slots=True)
class RunOutcome:
    run_id: str
    status: str
    success: bool
    duration_s: float
    turns: int
    test_runs: int
    final_patch: str
    final_test: TestResult
    parameters_json: str


def run_agent(
    client: Any,
    model: OllamaModel,
    ollama_version: str,
    manifest: TaskManifest,
    budget: BudgetConfig,
    store: ResultStore,
    is_demo: bool = False,
) -> RunOutcome:
    parameters = {
        "temperature": budget.temperature,
        "seed": budget.seed,
        "context_tokens": budget.context_tokens,
        "max_output_tokens": budget.max_output_tokens,
        "max_turns": budget.max_turns,
        "response_timeout_s": budget.response_timeout_s,
        "test_timeout_s": budget.test_timeout_s,
        "run_timeout_s": budget.run_timeout_s,
    }

    record = RunRecord.new(
        model_tag=model.name,
        model_digest=model.digest,
        ollama_version=ollama_version,
        task_id=manifest.task_id,
        category=manifest.category,
        parameters=parameters,
        instruction=manifest.instruction(),
        is_demo=is_demo,
    )
    store.start_run(record)

    start_time = time.monotonic()
    turn_count = 0
    terminal_status = None
    error_type = None
    error_message = None

    with WorkspaceExecutor.create(manifest, test_timeout_s=budget.test_timeout_s) as executor:
        initial_listing = executor.list_files().data.get("listing", "")
        system_prompt = build_system_prompt(budget)
        task_prompt = build_task_prompt(manifest, initial_listing)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt},
        ]

        schema = action_json_schema()

        while turn_count < budget.max_turns:
            elapsed = time.monotonic() - start_time
            if elapsed > budget.run_timeout_s:
                terminal_status = "run_timeout"
                error_type = "TimeoutError"
                error_message = f"Whole-run timeout of {budget.run_timeout_s}s exceeded"
                break

            turn_count += 1
            turn_start = time.monotonic()

            try:
                reply = client.chat(
                    model=model.name,
                    messages=messages,
                    temperature=budget.temperature,
                    seed=budget.seed,
                    context_tokens=budget.context_tokens,
                    max_output_tokens=budget.max_output_tokens,
                    response_schema=schema,
                )
            except Exception as err:
                terminal_status = "ollama_unavailable"
                error_type = type(err).__name__
                error_message = str(err)
                break

            response_text = reply.content
            action_req_json = {"raw_content": response_text}
            action_res_json: dict[str, Any] = {}
            action_type = "unknown"

            try:
                action = parse_action(response_text)
                action_type = action.action
                action_req_json["action"] = action_type

                exec_result: ActionResult = executor.execute(action)
                action_res_json = exec_result.data

                if isinstance(action, Finish):
                    obs_text = f"Action finished: {action.summary}"
                    messages.append({"role": "assistant", "content": response_text})
                    messages.append({"role": "user", "content": obs_text})
                    turn_duration = time.monotonic() - turn_start
                    store.append_action(
                        ActionRecord.new(
                            run_id=record.run_id,
                            turn=turn_count,
                            action_type=action_type,
                            request=action_req_json,
                            result=action_res_json,
                            duration_s=turn_duration,
                        )
                    )
                    break
                else:
                    obs_text = bounded_observation(json.dumps(exec_result.data, indent=2))

            except ProtocolError as err:
                action_type = "protocol_error"
                action_res_json = {"error": str(err)}
                obs_text = f"PROTOCOL ERROR: {err}. Please output a valid action JSON."
            except Exception as err:
                action_type = "executor_error"
                action_res_json = {"error": str(err)}
                obs_text = f"EXECUTION ERROR: {err}."

            turn_duration = time.monotonic() - turn_start
            store.append_action(
                ActionRecord.new(
                    run_id=record.run_id,
                    turn=turn_count,
                    action_type=action_type,
                    request=action_req_json,
                    result=action_res_json,
                    duration_s=turn_duration,
                )
            )

            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": obs_text})

        # Mandatory final verification
        final_test = executor.final_test()
        surviving_mutants = executor.surviving_mutants() if final_test.passed else []
        final_patch = executor.final_diff()
        test_runs = executor.test_run_count + 1

        total_duration = time.monotonic() - start_time

        success = final_test.passed and not surviving_mutants
        if success:
            status = "success"
        elif terminal_status:
            status = terminal_status
        elif final_test.timed_out:
            status = "test_timeout"
        elif final_test.exit_code == 0 and not final_test.passed:
            status = "invalid_test_report"
            error_type = "InvalidTestReport"
            error_message = f"pytest exited 0 without a clean JUnit report: {final_test.report}"
        elif surviving_mutants:
            status = "weak_tests"
            error_type = "WeakTests"
            error_message = f"Agent tests did not detect mutants: {', '.join(surviving_mutants)}"
        else:
            status = "tests_failed"

        store.finish_run(
            run_id=record.run_id,
            status=status,
            success=success,
            duration_s=total_duration,
            turns=turn_count,
            test_runs=test_runs,
            final_patch=final_patch,
            final_test_exit_code=final_test.exit_code,
            final_test_stdout=final_test.stdout,
            final_test_stderr=final_test.stderr,
            error_type=error_type,
            error_message=error_message,
        )

        return RunOutcome(
            run_id=record.run_id,
            status=status,
            success=success,
            duration_s=total_duration,
            turns=turn_count,
            test_runs=test_runs,
            final_patch=final_patch,
            final_test=final_test,
            parameters_json=record.parameters_json,
        )
