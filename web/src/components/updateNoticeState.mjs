export function showUpdate(status, dismissed) {
  return Boolean(status?.update_available && status?.latest && status?.release_url && status.latest !== dismissed);
}
export function readDismissed(storage) {
  try { return storage.getItem('cookdex.dismissedUpdate') || ''; } catch { return ''; }
}
export function dismissUpdate(storage, version) {
  try { storage.setItem('cookdex.dismissedUpdate', version); } catch { /* session dismissal still works */ }
  return version;
}

export function updateStorage() {
  try { return window.localStorage; } catch { return null; }
}
