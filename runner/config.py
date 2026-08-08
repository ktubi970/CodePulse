from dataclasses import dataclass
import ipaddress
from pathlib import Path
import socket
import tomllib
from urllib.parse import urlsplit


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OllamaConfig:
    base_url: str


@dataclass(frozen=True, slots=True)
class BudgetConfig:
    temperature: float = 0.0
    seed: int = 42
    context_tokens: int = 8192
    max_output_tokens: int = 1024
    max_turns: int = 12
    response_timeout_s: float = 120.0
    test_timeout_s: float = 30.0
    run_timeout_s: float = 1800.0


@dataclass(frozen=True, slots=True)
class AppConfig:
    ollama: OllamaConfig
    models: tuple[str, ...]
    tasks: tuple[str, ...]
    result_db: Path
    budget: BudgetConfig


def require_loopback_http(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname is None:
        raise ConfigError("Ollama URL must use plain HTTP on loopback")
    
    # Simple check for direct loopback IPs or localhost
    if parts.hostname in ("127.0.0.1", "localhost", "::1"):
        return

    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or 80)
        if not addresses or any(
            not ipaddress.ip_address(item[4][0]).is_loopback for item in addresses
        ):
            raise ConfigError("Ollama URL must resolve only to loopback")
    except Exception as err:
        raise ConfigError(f"Failed to resolve Ollama host '{parts.hostname}': {err}") from err


def load_config(path: Path) -> AppConfig:
    config_path = path.resolve()
    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception as err:
        raise ConfigError(f"Failed to parse TOML configuration: {err}") from err

    ollama_sec = data.get("ollama", {})
    base_url = ollama_sec.get("base_url", "http://127.0.0.1:11434")
    require_loopback_http(base_url)

    bench_sec = data.get("benchmark", {})
    models = tuple(bench_sec.get("models", []))
    if not models:
        raise ConfigError("Configured model list cannot be empty")

    tasks = tuple(bench_sec.get("tasks", []))

    rel_db = bench_sec.get("result_db", "results/codepulse.sqlite3")
    result_db = (config_path.parent / rel_db).resolve()

    # Budget values
    temp = float(bench_sec.get("temperature", 0.0))
    seed = int(bench_sec.get("seed", 42))
    ctx_tokens = int(bench_sec.get("context_tokens", 8192))
    max_output = int(bench_sec.get("max_output_tokens", 1024))
    max_turns = int(bench_sec.get("max_turns", 12))
    resp_timeout = float(bench_sec.get("response_timeout_s", 120.0))
    test_timeout = float(bench_sec.get("test_timeout_s", 30.0))
    run_timeout = float(bench_sec.get("run_timeout_s", 1800.0))

    if max_turns <= 0 or max_output <= 0 or ctx_tokens <= 0:
        raise ConfigError("Turn and token budgets must be positive integers")
    if resp_timeout <= 0 or test_timeout <= 0 or run_timeout <= 0:
        raise ConfigError("Timeouts must be positive numbers")

    budget = BudgetConfig(
        temperature=temp,
        seed=seed,
        context_tokens=ctx_tokens,
        max_output_tokens=max_output,
        max_turns=max_turns,
        response_timeout_s=resp_timeout,
        test_timeout_s=test_timeout,
        run_timeout_s=run_timeout,
    )

    return AppConfig(
        ollama=OllamaConfig(base_url=base_url),
        models=models,
        tasks=tasks,
        result_db=result_db,
        budget=budget,
    )
