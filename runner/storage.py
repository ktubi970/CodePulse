from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sqlite3
from typing import Any
import uuid


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    is_demo: bool
    model_tag: str
    model_digest: str
    ollama_version: str
    task_id: str
    category: str
    parameters_json: str
    instruction: str
    created_at: str
    platform_system: str
    python_version: str

    @classmethod
    def new(
        cls,
        model_tag: str,
        model_digest: str,
        ollama_version: str,
        task_id: str,
        category: str,
        parameters: dict[str, Any],
        instruction: str,
        is_demo: bool = False,
    ) -> "RunRecord":
        return cls(
            run_id=str(uuid.uuid4()),
            is_demo=is_demo,
            model_tag=model_tag,
            model_digest=model_digest,
            ollama_version=ollama_version,
            task_id=task_id,
            category=category,
            parameters_json=json.dumps(parameters, sort_keys=True),
            instruction=instruction,
            created_at=datetime.now(timezone.utc).isoformat(),
            platform_system=platform.platform(),
            python_version=platform.python_version(),
        )


@dataclass(frozen=True, slots=True)
class ActionRecord:
    run_id: str
    turn: int
    action_type: str
    request_json: str
    result_json: str
    created_at: str
    duration_s: float

    @classmethod
    def new(
        cls,
        run_id: str,
        turn: int,
        action_type: str,
        request: dict[str, Any],
        result: dict[str, Any],
        duration_s: float = 0.0,
    ) -> "ActionRecord":
        return cls(
            run_id=run_id,
            turn=turn,
            action_type=action_type,
            request_json=json.dumps(request, sort_keys=True),
            result_json=json.dumps(result, sort_keys=True),
            created_at=datetime.now(timezone.utc).isoformat(),
            duration_s=duration_s,
        )


class ResultStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # `with sqlite3.connect(...)` only commits; it never closes the connection.
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    is_demo INTEGER NOT NULL,
                    model_tag TEXT NOT NULL,
                    model_digest TEXT NOT NULL,
                    ollama_version TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 0,
                    duration_s REAL DEFAULT 0.0,
                    turns INTEGER DEFAULT 0,
                    test_runs INTEGER DEFAULT 0,
                    final_patch TEXT,
                    final_test_exit_code INTEGER,
                    final_test_stdout TEXT,
                    final_test_stderr TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    platform_system TEXT NOT NULL,
                    python_version TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS actions (
                    run_id TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    duration_s REAL DEFAULT 0.0,
                    PRIMARY KEY (run_id, turn),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model_tag);
                CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);
                CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
                CREATE INDEX IF NOT EXISTS idx_actions_run ON actions(run_id);
                """
            )

    def start_run(self, record: RunRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, is_demo, model_tag, model_digest, ollama_version,
                    task_id, category, parameters_json, instruction, created_at,
                    status, success, platform_system, python_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    1 if record.is_demo else 0,
                    record.model_tag,
                    record.model_digest,
                    record.ollama_version,
                    record.task_id,
                    record.category,
                    record.parameters_json,
                    record.instruction,
                    record.created_at,
                    "running",
                    0,
                    record.platform_system,
                    record.python_version,
                ),
            )

    def append_action(self, record: ActionRecord) -> None:
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO actions (
                        run_id, turn, action_type, request_json, result_json, created_at, duration_s
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.run_id,
                        record.turn,
                        record.action_type,
                        record.request_json,
                        record.result_json,
                        record.created_at,
                        record.duration_s,
                    ),
                )
            except sqlite3.IntegrityError as err:
                raise StorageError(f"Duplicate action turn {record.turn} for run {record.run_id}") from err

    def finish_run(
        self,
        run_id: str,
        status: str,
        success: bool,
        duration_s: float,
        turns: int,
        test_runs: int,
        final_patch: str | None = None,
        final_test_exit_code: int | None = None,
        final_test_stdout: str | None = None,
        final_test_stderr: str | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE runs SET
                    finished_at = ?,
                    status = ?,
                    success = ?,
                    duration_s = ?,
                    turns = ?,
                    test_runs = ?,
                    final_patch = ?,
                    final_test_exit_code = ?,
                    final_test_stdout = ?,
                    final_test_stderr = ?,
                    error_type = ?,
                    error_message = ?
                WHERE run_id = ? AND status = 'running'
                """,
                (
                    finished_at,
                    status,
                    1 if success else 0,
                    duration_s,
                    turns,
                    test_runs,
                    final_patch,
                    final_test_exit_code,
                    final_test_stdout,
                    final_test_stderr,
                    error_type,
                    error_message,
                    run_id,
                ),
            )
            if cursor.rowcount == 0:
                raise StorageError(f"Failed to finalize run {run_id}: run not found or already finished")

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None

            run_dict = dict(row)
            action_rows = conn.execute(
                "SELECT * FROM actions WHERE run_id = ? ORDER BY turn ASC", (run_id,)
            ).fetchall()
            run_dict["actions"] = [dict(a) for a in action_rows]
            return run_dict

    def finished_runs(self) -> list[dict[str, Any]]:
        """Real (non-demo) finished runs, oldest first, without their actions."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE is_demo = 0 AND status != 'running' ORDER BY created_at ASC, rowid ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
