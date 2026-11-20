import React from "react";

import { allSelected, withAll } from "./selectAll.mjs";

// One button beside a checkbox list's heading: "Select all" until everything
// is ticked, then "Select none". Hidden for lists with fewer than two items.
export default function SelectAllToggle({ keys, selected, onChange, label }) {
  if (keys.length < 2) return null;
  const all = allSelected(keys, selected);
  return (
    <button
      type="button"
      className="ghost small select-all-toggle"
      aria-label={label ? `${all ? "Select none" : "Select all"}: ${label}` : undefined}
      onClick={() => onChange(withAll(selected, keys, !all))}
    >
      {all ? "Select none" : "Select all"}
    </button>
  );
}
