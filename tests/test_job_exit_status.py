"""Exercise module exit status across the subprocess boundary used by jobs."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cookdex import data_maintenance


@pytest.mark.parametrize(('module', 'manager', 'args', 'failure_key'), [
    ('recipe_deduplicator', 'RecipeDeduplicator', [], 'failed'),
    ('recipe_junk_filter', 'RecipeJunkFilter', [], 'failed'),
    ('recipe_name_normalizer', 'RecipeNameNormalizer', [], 'failed'),
    ('recipe_reimporter', 'RecipeReimporter', [], 'failed'),
    ('yield_normalizer', 'YieldNormalizer', [], 'failed'),
    ('foods_manager', 'FoodsCleanupManager', ['cleanup'], 'actions_failed'),
    ('units_manager', 'UnitsCleanupManager', ['cleanup'], 'actions_failed'),
    ('taxonomy_duplicates', 'TaxonomyDuplicatesManager', ['cleanup'], 'actions_failed'),
    ('taxonomy_duplicates', 'TaxonomyDuplicatesManager', ['cleanup'], 'cookbooks_failed'),
])
@pytest.mark.parametrize('failures', [0, 1])
def test_module_exit_status(module, manager, args, failure_key, failures, tmp_path):
    # Replace only the worker's run method: parse real arguments and execute the
    # real __main__ block, without contacting Mealie or writing local reports.
    source = Path('src/cookdex', module + '.py').read_text()
    source = source.replace('if __name__ == "__main__":',
                            f'{manager}.run = lambda self: {{"summary": '
                            f'{{"failed": 0, "actions_failed": 0, "cookbooks_failed": 0, '
                            f'"{failure_key}": {failures}}}}}\n'
                            'if __name__ == "__main__":')
    script = tmp_path / 'entry.py'
    script.write_text(source.replace('from __future__ import annotations', 'from __future__ import annotations\n__package__ = "cookdex"'))
    env = {**os.environ, 'PYTHONPATH': str(Path('src').resolve()),
           'MEALIE_URL': 'http://127.0.0.1:1/api', 'MEALIE_API_KEY': 'test-token'}
    result = subprocess.run([sys.executable, str(script), *args], env=env, capture_output=True, text=True)
    assert result.returncode == bool(failures), result.stderr
    assert result.stderr == ''


@pytest.mark.parametrize('continue_on_error', [False, True])
def test_pipeline_with_failed_cleanup_subprocess(monkeypatch, tmp_path, continue_on_error):
    # Use the actual dedup worker and main; fail the remote deletion deliberately.
    source = Path('src/cookdex/recipe_deduplicator.py').read_text()
    setup = '''
class Client:
    def __init__(self, **kwargs): pass
    def get_recipes(self):
        return [dict(name=n, slug=n, orgURL="https://example.com/recipe") for n in ("one", "two")]
    def delete_recipe(self, slug): raise RuntimeError("injected deletion failure")
MealieApiClient = Client
resolve_mealie_url = lambda: "http://127.0.0.1:1/api"
resolve_mealie_api_key = lambda **kwargs: "test-token"
resolve_repo_path = lambda path: Path("report.json")
'''
    script = tmp_path / 'dedup.py'
    script.write_text(source.replace('from __future__ import annotations', 'from __future__ import annotations\n__package__ = "cookdex"').replace('if __name__ == "__main__":',
                                                                 setup + '\nif __name__ == "__main__":'))
    marker = tmp_path / 'next-stage'
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('DRY_RUN', 'false')
    monkeypatch.setenv('PYTHONPATH', str(Path(data_maintenance.__file__).resolve().parents[1]))
    monkeypatch.setattr(data_maintenance, 'stage_command', lambda stage, **kwargs:
                        [sys.executable, str(script), '--apply'] if stage == 'dedup' else
                        [sys.executable, '-c', 'from pathlib import Path; Path("next-stage").touch()'])
    results = data_maintenance.run_pipeline(['dedup', 'names'], continue_on_error=continue_on_error,
                                            apply_cleanups=True)
    assert results[0].exit_code == 1
    import json
    assert json.loads((tmp_path / 'report.json').read_text())['summary']['failed'] == 1
    assert marker.exists() == continue_on_error
