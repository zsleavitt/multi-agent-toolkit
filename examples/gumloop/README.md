# Gumloop examples (MAT-5)

Files in this folder support the **MAT-5** prototype described in `docs/prototypes/mat-5-gumloop.md`.

| File | Purpose |
|------|---------|
| `input-names.conventions.json` | Recommended Gumloop **Input** node `input_name` strings and short descriptions for MAT-aligned flows. |
| `start-pipeline.request.example.json` | Example **`start_pipeline`** JSON body (redact secrets; replace `saved_item_id` / `user_id`). |

Optional CLI (no extra deps): `python scripts/gumloop_start_pipeline.py --help` from repo root (requires `GUMLOOP_API_KEY` and `GUMLOOP_USER_ID`).

Use Gumloop’s docs for authentication and for mapping `pipeline_inputs` to your canvas Input nodes.
