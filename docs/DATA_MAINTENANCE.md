# Data Maintenance Pipeline

`data-maintenance` runs CookDex's cleanup and audit stages in a fixed order:

`dedup -> junk -> names -> parse -> foods -> units -> categorize -> yield -> quality -> audit`

Run the full pipeline for broad maintenance, or select individual stages when you only need a targeted operation.

## Recommended Flow

1. Open CookDex at `/cookdex`.
2. Go to **Tasks** and select **Data Maintenance Pipeline**.
3. Leave **Preview Run** enabled.
4. Choose specific stages only if you want a targeted run.
5. Run the task and review the log.
6. For live cleanup stages, switch to **Run Live**, enable **Apply Cleanup Writes**, and confirm the owner policy unlock.

## Stage Notes

| Stage | Purpose |
|---|---|
| `dedup` | Finds recipes imported from the same source URL. |
| `junk` | Detects non-recipe pages such as listicles, how-to posts, digests, placeholders, and bad scrapes. |
| `names` | Normalizes names derived from URL slugs. |
| `parse` | Parses raw ingredient lines into structured fields. |
| `foods`, `units` | Merges duplicate foods and units. Unit merges use each unit's abbreviation, plural and aliases in Mealie. |
| `categorize` | Applies rule-based organization and optional AI categorization. |
| `yield` | Normalizes yield and servings fields. |
| `quality` | Scores recipe completeness. |
| `audit` | Audits taxonomy usage and duplicates. |

The `labels`, `tools`, `taxonomy` and `cookbooks` stages were retired with the Taxonomy Editor. Saved schedules that still list them skip them and say so in the log. Edit those in **Organize**, or import a taxonomy file there.

## Scheduling

Create an interval schedule in the Web UI for recurring maintenance. Use a once schedule for a one-time future run.

For routine monitoring, schedule `data-maintenance` with **Preview Run** enabled or schedule `health-check` for a read-only report.
