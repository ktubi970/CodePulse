from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

import pytest

from agent.ollama import ModelMissing, OllamaClient
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
                    }
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
        if self.path == "/api/chat":
            content_len = int(self.headers.get("Content-Length", 0))
            req_body = self.rfile.read(content_len)
            data = json.loads(req_body.decode("utf-8"))
            payload = {
                "model": data.get("model"),
                "message": {"role": "assistant", "content": '{"action":"list_files"}'},
                "prompt_eval_count": 10,
                "eval_count": 5,
                "total_duration": 100000,
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

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
    assert len(models) == 1
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


def test_client_chat(server_url: str) -> None:
    client = OllamaClient(server_url, timeout_seconds=1)
    reply = client.chat(model="local:test", messages=[{"role": "user", "content": "hello"}])
    assert reply.content == '{"action":"list_files"}'
    assert reply.prompt_tokens == 10
    assert reply.completion_tokens == 5
