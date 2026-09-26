import test from 'node:test';
import assert from 'node:assert/strict';
import { showUpdate, readDismissed, dismissUpdate } from '../src/components/updateNoticeState.mjs';
test('update notice dismissal applies only to that version', () => {
  const data = new Map();
  const storage = {getItem: key => data.get(key), setItem: (key, val) => data.set(key, val)};
  const status = {update_available: true, latest: '2026.9.1', release_url: 'https://example.com/release'};
  assert.equal(showUpdate(status, readDismissed(storage)), true);
  dismissUpdate(storage, status.latest);
  assert.equal(showUpdate(status, readDismissed(storage)), false);
  assert.equal(showUpdate({...status, latest: '2026.10.0'}, readDismissed(storage)), true);
  assert.equal(showUpdate(null, ''), false);
  assert.equal(showUpdate({...status, update_available: false}, ''), false);
});
