import json
import sqlite3
from types import SimpleNamespace

import pytest

from cookdex.api_client import MealieApiClient
from cookdex.db_client import MealieDBClient
from cookdex.recipe_deduplicator import _group_duplicates
from cookdex.recipe_junk_filter import RecipeJunkFilter
from cookdex.recipe_reimporter import RecipeReimporter
from cookdex.taxonomy_manager import MealieTaxonomyManager


def test_replace_retains_ids_and_deletes_only_removed(monkeypatch):
    manager = MealieTaxonomyManager('http://example/api', 'test')
    monkeypatch.setattr(manager, 'existing_lookup', lambda _: {'dinner': {'id': 'keep', 'name': 'Dinner'},
                                                            'old': {'id': 'remove', 'name': 'Old'}})
    deleted = []
    monkeypatch.setattr(manager.session, 'delete', lambda url, **kw: deleted.append(url) or SimpleNamespace(status_code=200))
    monkeypatch.setattr(manager.session, 'post', lambda *a, **kw: pytest.fail('retained item recreated'))
    result = manager.import_items('tags', [{'name': 'Dinner'}], replace=True)
    assert result['skipped'] == 1
    assert deleted == ['http://example/api/organizers/tags/remove']


def test_replace_does_not_delete_after_failed_create(monkeypatch):
    manager = MealieTaxonomyManager('http://example/api', 'test')
    monkeypatch.setattr(manager, 'existing_lookup', lambda _: {'old': {'id': 'old', 'name': 'Old'}})
    monkeypatch.setattr(manager.session, 'post', lambda *a, **kw: SimpleNamespace(status_code=500, text='failure'))
    monkeypatch.setattr(manager.session, 'delete', lambda *a, **kw: pytest.fail('destructive cleanup after failure'))
    with pytest.raises(RuntimeError):
        manager.import_items('tags', [{'name': 'New'}], replace=True)


@pytest.mark.parametrize('name', ['Pantry Pasta', 'How to Make Rice', 'Cartwheel Pasta', 'Detox Water'])
def test_junk_preserves_complete_recipe(name, tmp_path):
    client = SimpleNamespace(get_recipes=lambda: [{'slug': 'recipe'}], get_recipe=lambda _: {
        'name': name, 'recipeIngredient': [{'note': '1 cup rice'}], 'recipeInstructions': [{'text': 'Cook rice.'}]},
        delete_recipe=lambda _: pytest.fail('valid recipe deleted'))
    report = RecipeJunkFilter(client, apply=True, dry_run=False, report_file=tmp_path/'report.json').run()
    assert report['summary']['deleted'] == 0


def test_dedup_does_not_prefer_copy_suffix():
    recipes = [dict(name=name, slug=str(i), orgURL='https://example.com/r') for i, name in enumerate(
        ['Rice', 'Rice (COPY)', 'Rice (copy 2)', 'Rice (2)'])]
    assert _group_duplicates(recipes)[0].keeper['name'] == 'Rice'


def test_resume_checkpoint_survives_preview_and_filters_before_limit(tmp_path):
    report = tmp_path/'report.json'
    report.write_text(json.dumps({'actions': [None, {'slug':'one','status':'reimported'}]}))
    recipes = [dict(slug=s, name=s, orgURL='https://example.com/'+s) for s in ('one','two','three')]
    worker = RecipeReimporter(SimpleNamespace(get_recipes=lambda: recipes), resume=True, max_recipes=1,
                             dry_run=False, delay=0, report_file=report)
    worker._process_one = lambda i,n,s,name,url: {'slug': s, 'status':'reimported'}
    worker.run()
    assert worker._load_completed() == {'one','two'}
    preview = RecipeReimporter(worker.client, resume=True, dry_run=True, report_file=report)
    preview.run()
    assert preview._load_completed() == {'one','two'}
    worker.run()
    assert worker._load_completed() == {'one','two','three'}
    worker.run()
    assert worker._load_completed() == {'one','two','three'}


def test_db_scope_authenticated_and_read_only(monkeypatch, tmp_path):
    path = tmp_path/'db.sqlite'
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE groups(id TEXT); INSERT INTO groups VALUES('first'),('second'); "
                       "CREATE TABLE users(id TEXT,group_id TEXT); INSERT INTO users VALUES('user','second'); "
                       "CREATE TABLE tags(slug TEXT,group_id TEXT);")
    conn.commit(); conn.close()
    monkeypatch.setenv('MEALIE_DB_TYPE','sqlite'); monkeypatch.setenv('MEALIE_SQLITE_PATH',str(path))
    monkeypatch.setenv('MEALIE_URL','http://example/api'); monkeypatch.setenv('MEALIE_API_KEY','test')
    monkeypatch.setattr(MealieApiClient, 'request_json', lambda *a, **kw: {'id':'user','groupId':'second'})
    with MealieDBClient() as db:
        assert db.get_group_id() == 'second'
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall() == []
    conn.close()
    monkeypatch.setattr(MealieApiClient, 'request_json', lambda *a, **kw: {'id':'missing','groupId':'second'})
    with MealieDBClient() as db, pytest.raises(RuntimeError):
        db.get_group_id()


def test_explicit_version_command_updates_lockfile(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location('bump_version', Path('scripts/bump_version.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = tmp_path/'package.json'; lock = tmp_path/'package-lock.json'
    package.write_text('{"version":"2026.9.0"}')
    lock.write_text('{"version":"2026.9.0","packages":{"":{"version":"2026.9.0"}}}')
    monkeypatch.setattr(module, 'PACKAGE_JSON', package)
    monkeypatch.setattr(module, 'PACKAGE_LOCK', lock)
    module.sync_package_json('2026.9.1')
    assert json.loads(package.read_text())['version'] == '2026.9.1'
    data = json.loads(lock.read_text())
    assert data['version'] == data['packages']['']['version'] == '2026.9.1'
