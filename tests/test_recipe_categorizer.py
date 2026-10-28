import types

import pytest

from cookdex.categorizer_core import ProviderUnavailableError
from cookdex import recipe_categorizer
from cookdex.recipe_categorizer import (
    cache_file_for_provider,
    derive_target_mode,
    query_anthropic,
    query_chatgpt,
    query_ollama,
    resolve_provider,
)


def test_resolve_provider_prefers_forced_provider():
    assert resolve_provider(cli_provider="chatgpt", forced_provider="chatgpt") == "chatgpt"


def test_resolve_provider_uses_cli_provider():
    assert resolve_provider(cli_provider="chatgpt") == "chatgpt"


def test_resolve_provider_accepts_anthropic():
    assert resolve_provider(cli_provider="anthropic") == "anthropic"


def test_resolve_provider_uses_config_default():
    assert resolve_provider() in {"ollama", "chatgpt", "anthropic"}


def test_resolve_provider_rejects_invalid():
    with pytest.raises(ValueError):
        resolve_provider(cli_provider="invalid")


def test_cache_file_for_provider_uses_config():
    assert cache_file_for_provider("ollama") == "cache/results_ollama.json"


def test_query_chatgpt_auth_error_fails_fast(monkeypatch):
    calls = []

    class _UnauthorizedResponse:
        status_code = 401
        headers = {}
        text = '{"error":{"message":"Incorrect API key provided"}}'

        def json(self):
            return {"error": {"message": "Incorrect API key provided"}}

        def raise_for_status(self):
            raise AssertionError("401 should raise ProviderUnavailableError before generic HTTP handling")

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return _UnauthorizedResponse()

    monkeypatch.setattr("cookdex.recipe_categorizer.requests.post", fake_post)

    with pytest.raises(ProviderUnavailableError, match="HTTP 401 Unauthorized"):
        query_chatgpt(
            "{}",
            "gpt-4o-mini",
            "https://api.openai.com/v1",
            "bad-key",
            request_timeout=1,
            http_retries=3,
        )

    assert len(calls) == 1


class _JsonResponse:
    status_code = 200
    headers = {}
    text = ""

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        return None


@pytest.mark.parametrize(
    "call, body",
    [
        # ChatGPT answers with no text (a refusal or tool call): content is null.
        (lambda: query_chatgpt("{}", "m", "https://api.test/v1", "k", request_timeout=1, http_retries=1),
         {"choices": [{"message": {"content": None}}]}),
        # Anthropic content blocks that aren't objects, or text that isn't a string.
        (lambda: query_anthropic("{}", "m", "https://api.test/v1", "k", request_timeout=1, http_retries=1, max_tokens=10),
         {"content": ["not-a-block"]}),
        (lambda: query_anthropic("{}", "m", "https://api.test/v1", "k", request_timeout=1, http_retries=1, max_tokens=10),
         {"content": [{"text": 5}]}),
        (lambda: query_anthropic("{}", "m", "https://api.test/v1", "k", request_timeout=1, http_retries=1, max_tokens=10),
         ["not", "an", "object"]),
        # Ollama replying with something other than an object.
        (lambda: query_ollama("{}", "m", "http://ollama.test/api", request_timeout=1, http_retries=1, options={}),
         ["not", "an", "object"]),
        (lambda: query_ollama("{}", "m", "http://ollama.test/api", request_timeout=1, http_retries=1, options={}),
         {"response": 5}),
    ],
)
def test_provider_odd_response_shapes_mean_no_answer(monkeypatch, call, body):
    monkeypatch.setattr("cookdex.recipe_categorizer.requests.post", lambda *a, **k: _JsonResponse(body))
    assert call() is None


def test_ollama_uses_smaller_default_batch_size(monkeypatch):
    monkeypatch.delenv("BATCH_SIZE", raising=False)
    monkeypatch.delenv("OLLAMA_BATCH_SIZE", raising=False)

    assert recipe_categorizer.batch_size_for_provider("ollama") == 1
    assert recipe_categorizer.batch_size_for_provider("chatgpt") == 50


def test_ollama_specific_batch_size_overrides_default(monkeypatch):
    monkeypatch.delenv("BATCH_SIZE", raising=False)
    monkeypatch.setenv("OLLAMA_BATCH_SIZE", "4")

    assert recipe_categorizer.batch_size_for_provider("ollama") == 4


def test_ollama_uses_safe_cpu_defaults(monkeypatch):
    captured = {}

    def fake_query_ollama(prompt_text, model, url, request_timeout, http_retries, options):
        captured["request_timeout"] = request_timeout
        captured.update(options)
        return "[]"

    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    monkeypatch.delenv("OLLAMA_NUM_CTX", raising=False)
    monkeypatch.delenv("OLLAMA_NUM_PREDICT", raising=False)
    monkeypatch.delenv("OLLAMA_NUM_THREAD", raising=False)
    monkeypatch.delenv("OLLAMA_REQUEST_TIMEOUT", raising=False)
    monkeypatch.setattr(recipe_categorizer, "query_ollama", fake_query_ollama)

    query_text, provider_name = recipe_categorizer.build_provider_query("ollama")
    assert provider_name == "Ollama (llama3.1:8b)"

    query_text("prompt")

    assert captured["request_timeout"] == 300
    assert captured["num_ctx"] == 2048
    assert captured["num_predict"] == 512
    assert captured["num_thread"] == 4


def test_derive_target_mode():
    assert derive_target_mode(types.SimpleNamespace(missing_tags=True, missing_categories=False, missing_tools=False)) == "missing-tags"
    assert derive_target_mode(types.SimpleNamespace(missing_tags=False, missing_categories=True, missing_tools=False)) == "missing-categories"
    assert derive_target_mode(types.SimpleNamespace(missing_tags=False, missing_categories=False, missing_tools=True)) == "missing-tools"
    assert derive_target_mode(types.SimpleNamespace(missing_tags=True, missing_categories=False, missing_tools=True)) == "missing-either"
    assert derive_target_mode(types.SimpleNamespace(missing_tags=False, missing_categories=False, missing_tools=False)) == "missing-either"


def _ollama(monkeypatch, replies):
    sent = []

    def post(url, json=None, **kwargs):
        sent.append(json)
        return replies.pop(0)

    monkeypatch.setattr("cookdex.recipe_categorizer.requests.post", post)
    answer = query_ollama("{}", "qwen3", "http://ollama.test/api", request_timeout=1, http_retries=2, options={})
    return answer, sent


def test_ollama_asks_reasoning_models_not_to_think(monkeypatch):
    answer, sent = _ollama(monkeypatch, [_JsonResponse({"response": '[{"slug": "soup"}]'})])
    assert sent[0]["think"] is False
    assert answer == '[{"slug": "soup"}]'


def test_ollama_reply_drops_an_inline_think_block(monkeypatch):
    reply = _JsonResponse({"response": '<think>\nThe soup is a main course...\n</think>\n[{"slug": "soup"}]'})
    answer, _ = _ollama(monkeypatch, [reply])
    assert answer == '[{"slug": "soup"}]'


def test_ollama_retries_without_think_when_the_server_rejects_it(monkeypatch):
    rejected = _JsonResponse({"error": "invalid option: think"})
    rejected.status_code = 400
    rejected.text = '{"error": "invalid option: think"}'
    answer, sent = _ollama(monkeypatch, [rejected, _JsonResponse({"response": "[]"})])
    assert answer == "[]"
    assert "think" in sent[0] and "think" not in sent[1]


@pytest.mark.parametrize(
    "address",
    ["http://ollama.test:11434", "http://ollama.test:11434/", "http://ollama.test:11434/api", "http://ollama.test:11434/api/tags"],
)
def test_ollama_posts_to_the_api_whatever_address_form_was_entered(monkeypatch, address):
    called = []

    def post(url, json=None, **kwargs):
        called.append(url)
        return _JsonResponse({"response": "[]"})

    monkeypatch.setattr("cookdex.recipe_categorizer.requests.post", post)
    query_ollama("{}", "qwen3", address, request_timeout=1, http_retries=1, options={})
    assert called == ["http://ollama.test:11434/api/generate"]


def _not_found(body):
    response = _JsonResponse(body)
    response.status_code = 404
    return response


def test_ollama_404_for_a_missing_route_points_at_the_address(monkeypatch):
    with pytest.raises(ProviderUnavailableError, match="Check the Ollama address"):
        _ollama(monkeypatch, [_not_found(None)])


def test_ollama_404_for_a_missing_model_says_to_pull_it(monkeypatch):
    with pytest.raises(ProviderUnavailableError, match="ollama pull qwen3"):
        _ollama(monkeypatch, [_not_found({"error": "model 'qwen3' not found"})])
