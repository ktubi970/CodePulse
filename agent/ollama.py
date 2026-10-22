from dataclasses import dataclass
import http.client
import json
from typing import Any
from urllib.parse import urlsplit

from runner.config import require_loopback_http


@dataclass(frozen=True, slots=True)
class OllamaModel:
    name: str
    digest: str
    parameter_size: str
    quantization: str


@dataclass(frozen=True, slots=True)
class OllamaReply:
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_duration_ns: int


class OllamaUnavailable(RuntimeError):
    pass


class OllamaTimeout(OllamaUnavailable):
    pass


class ModelMissing(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: float = 120.0) -> None:
        require_loopback_http(base_url)
        parts = urlsplit(base_url)
        self._host = parts.hostname or "127.0.0.1"
        self._port = parts.port or 11434
        self.timeout_seconds = timeout_seconds

    def _request(self, method: str, path: str, body: bytes | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"} if body is not None else {}
        conn = http.client.HTTPConnection(self._host, self._port, timeout=self.timeout_seconds)
        try:
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            raw_data = response.read(4 * 1024 * 1024)  # 4 MiB max

            if response.status != 200:
                raise OllamaUnavailable(
                    f"Ollama server returned HTTP {response.status}: {raw_data.decode('utf-8', errors='replace')}"
                )

            return json.loads(raw_data.decode("utf-8"))
        except OllamaUnavailable:
            raise
        except TimeoutError as err:
            raise OllamaTimeout(
                f"Ollama did not answer {method} {path} within {self.timeout_seconds}s"
            ) from err
        except Exception as err:
            raise OllamaUnavailable(f"Ollama communication error at {self._host}:{self._port}: {err}") from err
        finally:
            conn.close()

    def version(self) -> str:
        data = self._request("GET", "/api/version")
        return str(data.get("version", "unknown"))

    def list_models(self) -> tuple[OllamaModel, ...]:
        data = self._request("GET", "/api/tags")
        raw_models = data.get("models", [])
        models = []
        for item in raw_models:
            details = item.get("details", {})
            models.append(
                OllamaModel(
                    name=item.get("name", ""),
                    digest=item.get("digest", ""),
                    parameter_size=details.get("parameter_size", ""),
                    quantization=details.get("quantization_level", ""),
                )
            )
        return tuple(models)

    def require_model(self, model_tag: str) -> OllamaModel:
        # /api/tags always reports full tags; a bare name means the ":latest" tag.
        wanted = model_tag if ":" in model_tag else f"{model_tag}:latest"
        for m in self.list_models():
            if m.name == wanted:
                return m
        raise ModelMissing(f"Configured model tag '{model_tag}' is absent from local Ollama library")

    def load_model(self, model: str) -> None:
        """Load the weights before the first timed turn (a generate request without prompt)."""
        self._request("POST", "/api/generate", body=json.dumps({"model": model}).encode("utf-8"))

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        seed: int = 42,
        context_tokens: int = 8192,
        max_output_tokens: int = 1024,
        response_schema: dict[str, Any] | None = None,
    ) -> OllamaReply:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "seed": seed,
                "num_ctx": context_tokens,
                "num_predict": max_output_tokens,
            },
        }
        if response_schema is not None:
            payload["format"] = response_schema

        body_bytes = json.dumps(payload).encode("utf-8")
        res = self._request("POST", "/api/chat", body=body_bytes)

        msg = res.get("message", {})
        content = msg.get("content", "")
        prompt_eval = int(res.get("prompt_eval_count", 0))
        eval_count = int(res.get("eval_count", 0))
        total_duration = int(res.get("total_duration", 0))

        return OllamaReply(
            content=content,
            prompt_tokens=prompt_eval,
            completion_tokens=eval_count,
            total_duration_ns=total_duration,
        )
