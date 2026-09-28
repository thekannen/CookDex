from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from cookdex.webui_server.update_check import UpdateChecker, calver
from cookdex.webui_server.routers.meta import get_about_meta


@pytest.mark.parametrize(('value', 'expected'), [('v2026.10.0', (2026, 10, 0)),
    ('2026.9.1', (2026, 9, 1)), ('v2026.9.2-beta.1', (2026, 9, 2)), ('2026.9.2-', None),
    ('2026.13.0', None), ('garbage', None)])
def test_calver(value, expected):
    assert calver(value) == expected


def session(monkeypatch, *, error=None, status=200, payload=None):
    response = Mock(status_code=status)
    response.raise_for_status.side_effect = error
    response.json.return_value = payload or {'tag_name': 'v2026.10.0'}
    client = Mock()
    client.get.return_value = response
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(requests, 'Session', lambda: client)
    return client


def test_success_cache_and_disabled(monkeypatch):
    client = session(monkeypatch)
    enabled = False
    check = UpdateChecker(lambda: enabled, current='2026.9.0')
    check.check()
    client.get.assert_not_called()
    enabled = True
    check.check()
    check.check()
    client.get.assert_called_once()
    assert client.trust_env is False
    assert client.get.call_args.kwargs['headers']['User-Agent'] == 'CookDex/2026.9.0'
    assert check.status()['update_available'] is True
    assert check.status()['latest'] == '2026.10.0'
    assert check.status()['release_url'].endswith('/v2026.10.0')
    assert check.status()['checked_at']
    check._next_check = 0
    check.check()
    assert client.get.call_count == 2
    enabled = False
    assert check.status()['latest'] is None


@pytest.mark.parametrize('status', [403, 429, 500])
def test_errors_cached_as_unknown(monkeypatch, status):
    client = session(monkeypatch, status=status, error=requests.HTTPError('unavailable'))
    check = UpdateChecker(lambda: True, current='2026.9.0')
    check.check()
    check.check()
    assert check.status()['latest'] is None
    assert not check.status()['update_available']
    client.get.assert_called_once()


def test_timeout_and_invalid_releases(monkeypatch):
    client = session(monkeypatch)
    client.get.side_effect = requests.Timeout()
    check = UpdateChecker(lambda: True, current='2026.9.0')
    check.check()
    assert check.status()['latest'] is None
    for payload in ({'tag_name': 'v2026.10.0', 'prerelease': True}, {'tag_name': 'v2026.10.0', 'draft': True},
                    {'tag_name': 'bad'}, []):
        session(monkeypatch, payload=payload or ['invalid'])
        check._next_check = 0
        check.check()
        assert not check.status()['update_available']


def test_meta_payload(monkeypatch):
    session(monkeypatch, payload={'tag_name': 'v2026.9.0'})
    check = UpdateChecker(lambda: True, current='2026.9.1')
    check.check()
    state = SimpleNamespace(**{name: lambda: 0 for name in ('count_users','count_runs','count_schedules')})
    services = SimpleNamespace(update_checker=check, state=state, registry=SimpleNamespace(task_ids=[]))
    payload = get_about_meta(_session={}, services=services)
    assert payload['update']['current'] == '2026.9.1'
    assert payload['update']['latest'] == '2026.9.0'
    assert not payload['update']['update_available']


def test_beta_installs_are_told_about_the_final_release(monkeypatch):
    session(monkeypatch, payload={'tag_name': 'v2026.9.2'})
    check = UpdateChecker(lambda: True, current='2026.9.2-beta.1')
    check.check()
    assert check.status()['update_available'] is True
    assert check.status()['latest'] == '2026.9.2'


def test_a_beta_is_never_offered_as_the_latest_release(monkeypatch):
    session(monkeypatch, payload={'tag_name': 'v2026.9.3-beta.1'})
    check = UpdateChecker(lambda: True, current='2026.9.1')
    check.check()
    assert check.status()['update_available'] is False
