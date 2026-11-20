// Select all / Select none for a list of checkboxes. `keys` are the items in
// the list that can be ticked; anything disabled is left out by the caller.

export function allSelected(keys, selected) {
  return keys.length > 0 && keys.every((key) => selected.has(key));
}

// A new set with every key ticked (on) or unticked (off); other keys are kept.
export function withAll(selected, keys, on) {
  const next = new Set(selected);
  for (const key of keys) {
    if (on) next.add(key);
    else next.delete(key);
  }
  return next;
}
