from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
import time

import pytest

from agent.ollama import ModelMissing, OllamaClient, OllamaRequestError, OllamaTimeout, OllamaUnavailable
from runner.config import ConfigError


class MockOllamaHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/version":
            payload = {"version": "0.test"}
        elif self.path == "/api/tags":
            payload = {
                "models": [
                    {
                        "name": "local:test",
                        "digest": "abc123digest",
                        "details": {"parameter_size": "1.5B", "quantization_level": "Q4_0"},
                    },
                    {"name": "plain:latest", "digest": "def456", "details": {}},
                ]
            }
        else:
            self.send_error(404)
            return

        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(content_len).decode("utf-8"))
        if self.path == "/api/generate":
            MockOllamaHandler.loaded.append(data)
            payload: dict[str, object] = {"model": data.get("model"), "done": True}
        elif self.path == "/api/chat":
            if data.get("model") == "slow:test":
                time.sleep(2)
            if data.get("model") == "loop:test":
                body = b'{"error":"prediction aborted, token repeat limit reached"}'
                self.send_response(500)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            payload = {
                "model": data.get("model"),
                "message": {"role": "assistant", "content": '{"action":"list_files"}'},
                "prompt_eval_count": 10,
                "eval_count": 5,
                "total_duration": 100000,
            }
        else:
            self.send_error(404)
            return
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    loaded: list[dict[str, object]] = []

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def server_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockOllamaHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_client_reads_version_and_tags_from_loopback(server_url: str) -> None:
    client = OllamaClient(server_url, timeout_seconds=1)
    assert client.version() == "0.test"
    models = client.list_models()
    assert len(models) == 2
    assert models[0].name == "local:test"
    assert models[0].digest == "abc123digest"


def test_client_rejects_external_url() -> None:
    with pytest.raises(ConfigError, match="loopback"):
        OllamaClient("http://example.com:11434")


def test_require_model_never_pulls_missing_tag(server_url: str) -> None:
    client = OllamaClient(server_url, timeout_seconds=1)
    model = client.require_model("local:test")
    assert model.name == "local:test"

    with pytest.raises(ModelMissing, match="missing:test"):
        client.require_model("missing:test")


def test_require_model_resolves_implicit_latest_tag(server_url: str) -> None:
    # /api/tags always reports full tags, so a bare name means "<name>:latest".
    client = OllamaClient(server_url, timeout_seconds=1)
    assert client.require_model("plain").name == "plain:latest"


def test_chat_timeout_is_reported_as_timeout(server_url: str) -> None:
    client = OllamaClient(server_url, timeout_seconds=0.3)
    with pytest.raises(OllamaTimeout):
        client.chat(model="slow:test", messages=[{"role": "user", "content": "hello"}])


def test_error_response_is_not_an_outage(server_url: str) -> None:
    # The server answered: the request failed, not the infrastructure.
    client = OllamaClient(server_url, timeout_seconds=1)
    with pytest.raises(OllamaRequestError, match="token repeat limit") as exc_info:
        client.chat(model="loop:test", messages=[{"role": "user", "content": "hello"}])
    assert not isinstance(exc_info.value, OllamaUnavailable)


def test_refused_connection_is_an_outage() -> None:
    with pytest.raises(OllamaUnavailable):
        OllamaClient("http://127.0.0.1:9", timeout_seconds=1).version()


def test_load_model_preloads_without_prompt(server_url: str) -> None:
    MockOllamaHandler.loaded.clear()
    OllamaClient(server_url, timeout_seconds=1).load_model("local:test")
    assert MockOllamaHandler.loaded == [{"model": "local:test"}]


def test_client_chat(server_url: str) -> None:
    client = OllamaClient(server_url, timeout_seconds=1)
    reply = client.chat(model="local:test", messages=[{"role": "user", "content": "hello"}])
    assert reply.content == '{"action":"list_files"}'
    assert reply.prompt_tokens == 10
    assert reply.completion_tokens == 5
