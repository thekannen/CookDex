from __future__ import annotations

import requests
import pytest

from cookdex.api_client import MealieApiClient


def _http_404_error(message: str) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = 404
    return requests.HTTPError(message, response=response)


def _http_422_error(message: str) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = 422
    return requests.HTTPError(message, response=response)


def test_create_food_uses_current_schema_before_legacy_group_id(monkeypatch):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, path_or_url: str, **kwargs):
        calls.append((method, path_or_url, kwargs.get("json")))
        if method == "POST" and path_or_url == "/foods":
            return {"id": "food-1", "name": kwargs["json"]["name"]}
        raise AssertionError(f"Unexpected request: {method} {path_or_url}")

    monkeypatch.setattr(client, "request_json", fake_request_json)

    created = client.create_food("Apple", group_id="legacy-group")
    assert created == {"id": "food-1", "name": "Apple"}
    assert calls == [("POST", "/foods", {"name": "Apple"})]


def test_create_food_falls_back_to_legacy_group_id_on_validation_error(monkeypatch):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, path_or_url: str, **kwargs):
        calls.append((method, path_or_url, kwargs.get("json")))
        if method == "POST" and path_or_url == "/foods":
            payload = kwargs["json"]
            if payload == {"name": "Apple"}:
                raise _http_422_error("groupId required")
            if payload == {"name": "Apple", "groupId": "legacy-group"}:
                return {"id": "food-1", "name": "Apple", "groupId": "legacy-group"}
        raise AssertionError(f"Unexpected request: {method} {path_or_url}")

    monkeypatch.setattr(client, "request_json", fake_request_json)

    created = client.create_food("Apple", group_id="legacy-group")
    assert created == {"id": "food-1", "name": "Apple", "groupId": "legacy-group"}
    assert calls == [
        ("POST", "/foods", {"name": "Apple"}),
        ("POST", "/foods", {"name": "Apple", "groupId": "legacy-group"}),
    ]


def test_merge_food_uses_current_payload_without_legacy_probes(monkeypatch):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, path_or_url: str, **kwargs):
        calls.append((method, path_or_url, kwargs.get("json")))
        return {"message": "merged", "error": False}

    monkeypatch.setattr(client, "request_json", fake_request_json)

    result = client.merge_food("source-food", "target-food")
    assert result == {"message": "merged", "error": False}
    assert calls == [
        ("PUT", "/foods/merge", {"fromFood": "source-food", "toFood": "target-food"})
    ]


def test_merge_unit_uses_current_payload_without_legacy_probes(monkeypatch):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, path_or_url: str, **kwargs):
        calls.append((method, path_or_url, kwargs.get("json")))
        return {"message": "merged", "error": False}

    monkeypatch.setattr(client, "request_json", fake_request_json)

    result = client.merge_unit("source-unit", "target-unit")
    assert result == {"message": "merged", "error": False}
    assert calls == [
        ("PUT", "/units/merge", {"fromUnit": "source-unit", "toUnit": "target-unit"})
    ]


def test_list_tools_falls_back_to_organizers_route(monkeypatch):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    calls: list[str] = []

    def fake_get_paginated(path_or_url: str, *, per_page: int = 1000, timeout: int | None = None):
        calls.append(path_or_url)
        if path_or_url == "/organizers/tools":
            raise _http_404_error("missing /organizers/tools")
        if path_or_url == "/tools":
            return [{"id": "tool-1", "name": "Blender"}]
        raise AssertionError(f"Unexpected path: {path_or_url}")

    monkeypatch.setattr(client, "get_paginated", fake_get_paginated)
    result = client.list_tools()
    assert result == [{"id": "tool-1", "name": "Blender"}]
    assert calls == ["/organizers/tools", "/tools"]


def test_create_tool_falls_back_to_organizers_route(monkeypatch):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, path_or_url: str, **kwargs):
        calls.append((method, path_or_url, kwargs.get("json")))
        if method == "POST" and path_or_url == "/organizers/tools":
            raise _http_404_error("missing /organizers/tools")
        if method == "POST" and path_or_url == "/tools":
            return {"id": "tool-2", "name": kwargs["json"]["name"]}
        raise AssertionError(f"Unexpected request: {method} {path_or_url}")

    monkeypatch.setattr(client, "request_json", fake_request_json)

    created = client.create_tool("Dutch Oven")
    assert created == {"id": "tool-2", "name": "Dutch Oven"}
    assert calls == [
        ("POST", "/organizers/tools", {"name": "Dutch Oven", "householdsWithTool": []}),
        ("POST", "/tools", {"name": "Dutch Oven"}),
    ]


def test_merge_tool_moves_recipe_links_when_merge_route_missing(monkeypatch):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    calls: list[tuple[str, str, object]] = []

    def fake_request_json(method, route, **kwargs):
        calls.append((method, route, kwargs.get("json")))
        raise _http_404_error(f"missing {route}")

    monkeypatch.setattr(client, "request_json", fake_request_json)
    source = {"id": "source", "name": "Pot", "slug": "pot"}
    target = {"id": "target", "name": "Pan", "slug": "pan"}
    other = {"id": "other", "name": "Spoon", "slug": "spoon"}
    recipe = {"id": "recipe", "tools": [source, other]}
    deleted = []
    monkeypatch.setattr(client, "list_tools", lambda: [source, target, other])
    monkeypatch.setattr(client, "get_paginated", lambda *a, **kw: [recipe.copy()])
    monkeypatch.setattr(client, "get_recipe", lambda ref: recipe.copy())
    monkeypatch.setattr(client, "patch_recipe", lambda ref, payload: recipe.update(payload))
    monkeypatch.setattr(client, "count_paginated", lambda *a, **kw: 0)
    monkeypatch.setattr(client, "delete_organizer_item", lambda *args: deleted.append(args))
    assert client.merge_tool("source", "target") == {"merged": 1}
    assert recipe["tools"] == [other, target]
    assert deleted == [("tools", "source")]
    payload = {"fromId": "source", "toId": "target"}
    assert calls == [("POST", "/organizers/tools/merge", payload), ("POST", "/tools/merge", payload)]


@pytest.mark.parametrize('failure', ['write', 'verification', 'remaining'])
def test_tool_merge_keeps_source_when_recipe_movement_is_not_complete(monkeypatch, failure):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    monkeypatch.setattr(client, 'request_json', lambda *a, **kw: (_ for _ in ()).throw(_http_error(404)))
    source, target = {'id': 'source'}, {'id': 'target'}
    recipe = {'id': 'recipe', 'tools': [source]}
    monkeypatch.setattr(client, 'list_tools', lambda: [source, target])
    monkeypatch.setattr(client, 'get_paginated', lambda *a, **kw: [recipe.copy()])
    monkeypatch.setattr(client, 'get_recipe', lambda ref: recipe.copy())
    def patch(ref, payload):
        if failure == 'write': raise requests.ConnectionError('injected outage')
        if failure != 'verification': recipe.update(payload)
    monkeypatch.setattr(client, 'patch_recipe', patch)
    monkeypatch.setattr(client, 'count_paginated', lambda *a, **kw: 1)
    deleted = []
    monkeypatch.setattr(client, 'delete_organizer_item', lambda *a: deleted.append(a))
    with pytest.raises(requests.RequestException): client.merge_tool('source', 'target')
    assert not deleted


def test_merge_tool_tries_fallback_route_on_405(monkeypatch):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    calls: list[str] = []

    def fake_request_json(method, route, **kwargs):
        calls.append(route)
        if route == "/organizers/tools/merge":
            raise _http_error(405)
        return {"message": "merged"}

    monkeypatch.setattr(client, "request_json", fake_request_json)
    assert client.merge_tool("source", "target") == {"message": "merged"}
    assert calls == ["/organizers/tools/merge", "/tools/merge"]


def test_merge_tool_raises_real_errors_after_one_request(monkeypatch):
    """A 422 or 500 is the server's answer, not a reason to probe other payloads or routes."""
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    for status in (422, 500):
        calls: list[str] = []

        def fake_request_json(method, route, **kwargs):
            calls.append(route)
            raise _http_error(status, b'{"detail": "bad"}')

        monkeypatch.setattr(client, "request_json", fake_request_json)
        with pytest.raises(requests.HTTPError, match=rf"failed \({status}\)"):
            client.merge_tool("source", "target")
        assert calls == ["/organizers/tools/merge"]


def test_count_paginated_uses_reported_total(monkeypatch):
    """A count-only collection must not be paginated down in full."""
    from cookdex.api_client import MealieApiClient

    client = MealieApiClient(base_url="http://mealie.test", api_key="k")
    calls: list[str] = []

    def fake_request_json(method, url, **kwargs):
        calls.append(url)
        return {"items": [{"name": "one"}], "total": 4210, "next": None}

    monkeypatch.setattr(client, "request_json", fake_request_json)

    assert client.count_paginated("/foods") == 4210
    assert len(calls) == 1
    assert "perPage=1" in calls[0]


def test_count_paginated_falls_back_when_total_absent(monkeypatch):
    """Servers that omit 'total' still get a correct count."""
    from cookdex.api_client import MealieApiClient

    client = MealieApiClient(base_url="http://mealie.test", api_key="k")

    def fake_request_json(method, url, **kwargs):
        if "perPage=1&" in url or url.endswith("perPage=1"):
            return {"items": [{"name": "a"}], "next": None}
        return {"items": [{"name": "a"}, {"name": "b"}, {"name": "c"}], "next": None}

    monkeypatch.setattr(client, "request_json", fake_request_json)
    assert client.count_paginated("/foods") == 3


def test_connection_pool_is_sized_for_worker_threads():
    from cookdex.api_client import MealieApiClient

    client = MealieApiClient(base_url="http://mealie.test", api_key="k")
    adapter = client.session.get_adapter("http://mealie.test")
    assert adapter._pool_maxsize >= 20


def _http_error(status: int, body: bytes = b"") -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response._content = body
    return requests.HTTPError(f"failed ({status})", response=response)


def test_merge_organizer_item_posts_single_payload(monkeypatch):
    client = MealieApiClient(base_url="http://mealie.local/api", api_key="token")
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, path_or_url: str, **kwargs):
        calls.append((method, path_or_url, kwargs.get("json")))
        return None

    monkeypatch.setattr(client, "request_json", fake_request_json)

    assert client.merge_organizer_item("tags", "src", "dst") == {}
    assert calls == [("POST", "/organizers/tags/merge", {"fromId": "src", "toId": "dst"})]


def test_is_missing_route_distinguishes_old_server_from_missing_record():
    assert MealieApiClient.is_missing_route(_http_error(405, b'{"detail":"Method Not Allowed"}'))
    assert MealieApiClient.is_missing_route(_http_error(404, b'{"detail":"Not Found"}'))
    assert MealieApiClient.is_missing_route(_http_error(404, b"<html>nope</html>"))
    assert not MealieApiClient.is_missing_route(_http_error(404, b'{"detail":"from_id tag not found"}'))
    assert not MealieApiClient.is_missing_route(_http_error(422, b'{"detail":[]}'))
    assert not MealieApiClient.is_missing_route(requests.HTTPError("connection reset"))


# What Mealie v3.28 answers for GET /foods/empty: the path falls through to /foods/{item_id}.
_OLD_EMPTY = b'{"detail":[{"type":"uuid_parsing","loc":["path","item_id"],"msg":"Input should be a valid UUID","input":"empty"}]}'


@pytest.mark.parametrize("status,body", [(422, _OLD_EMPTY), (404, b'{"detail":"Not Found"}'), (405, b'{"detail":"Method Not Allowed"}')])
def test_get_empty_is_none_on_servers_without_the_route_and_asks_once(monkeypatch, status, body):
    client = MealieApiClient(base_url="http://example/api", api_key="x")
    calls = []

    def fake_request_json(method, path, **kwargs):
        calls.append(path)
        raise _http_error(status, body)

    monkeypatch.setattr(client, "request_json", fake_request_json)
    assert client.get_empty("/foods/empty") is None
    assert client.get_empty("/foods/empty") is None
    assert calls == ["/foods/empty"]


def test_get_empty_returns_mealies_list_and_raises_other_errors(monkeypatch):
    client = MealieApiClient(base_url="http://example/api", api_key="x")
    monkeypatch.setattr(client, "request_json", lambda *a, **kw: [{"id": "f1", "name": "unused"}])
    assert client.get_empty("/foods/empty") == [{"id": "f1", "name": "unused"}]

    # A validation error on the body, or a server error, isn't a missing route.
    for status, body in ((422, b'{"detail":[{"loc":["query","perPage"]}]}'), (500, b"oops")):
        monkeypatch.setattr(client, "request_json", lambda *a, _s=status, _b=body, **kw: (_ for _ in ()).throw(_http_error(_s, _b)))
        with pytest.raises(requests.HTTPError):
            client.get_empty("/groups/labels/empty")


def test_merge_label_uses_mealies_route_and_is_none_without_it(monkeypatch):
    client = MealieApiClient(base_url="http://example/api", api_key="x")
    seen = []

    def native(method, path, json=None, **kwargs):
        seen.append((method, path, json))
        return {"id": "target"}

    monkeypatch.setattr(client, "request_json", native)
    assert client.merge_label("source", "target") == {"id": "target"}
    assert seen == [("POST", "/groups/labels/merge", {"fromId": "source", "toId": "target"})]

    monkeypatch.setattr(client, "request_json", lambda *a, **kw: (_ for _ in ()).throw(_http_error(405, b'{"detail":"Method Not Allowed"}')))
    assert client.merge_label("source", "target") is None

    # v3.29 with a label that's gone: its real answer, not a fallback.
    monkeypatch.setattr(client, "request_json", lambda *a, **kw: (_ for _ in ()).throw(_http_error(404, b'{"detail":"from_id label not found"}')))
    with pytest.raises(requests.HTTPError):
        client.merge_label("source", "target")
